import asyncio
import hashlib
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.deepseek import deepseek_client
from app.api.deps import get_current_user, get_wall_access_token
from app.db import SessionLocal, get_db
from app.models import Card, Reaction, User, Wall
from app.schemas.card import CardCreate, CardMoveCommit, CardUpdate, ReactionToggle
from app.services.action_log import log_action
from app.services.content_validation import ContentValidationError, validate_card_content
from app.services.placeholders import placeholder_manager
from app.services.placement import PlacedCard, find_nearest_legal
from app.services.serializers import card_to_public
from app.services.wall_access import has_wall_access
from app.websocket.manager import manager


router = APIRouter(prefix="/walls/{wall_id}/cards", tags=["cards"])

COLORS = ["purple", "green", "blue", "pink", "yellow", "beige"]
REACTION_EQUIVALENTS = {
    "like": ["like", "idea"],
    "dislike": ["dislike", "fire"],
    "question": ["question"],
}


def _content_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_content_or_422(content_json: dict, plain_text: str | None = None) -> str:
    try:
        return validate_card_content(content_json, plain_text)
    except ContentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _require_wall(db: Session, wall_id: str, user: User | None = None, wall_access_token: str | None = None) -> Wall:
    wall = db.get(Wall, wall_id)
    if not wall or wall.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    if not has_wall_access(wall, wall_access_token, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wall password required")
    return wall


def _require_unlocked_for_member(wall: Wall, user: User) -> None:
    if wall.is_locked and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wall is locked")


def _placed_cards(db: Session, wall_id: str) -> list[PlacedCard]:
    cards = db.scalars(select(Card).where(Card.wall_id == wall_id, Card.is_deleted == False)).all()  # noqa: E712
    return [PlacedCard(id=card.id, x=card.x, y=card.y, width=card.width, height=card.height) for card in cards]


async def _analyze_later(card_id: str, expected_fingerprint: str) -> None:
    with SessionLocal() as db:
        card = db.get(Card, card_id)
        if not card:
            return
        if card.is_deleted or _content_fingerprint(card.plain_text) != expected_fingerprint:
            return
        wall = db.get(Wall, card.wall_id)
        if not wall or not wall.ai_enabled:
            return
        text = card.plain_text
        ai_model = wall.ai_model
        ai_thinking_enabled = wall.ai_thinking_enabled
        ai_reasoning_effort = wall.ai_reasoning_effort
    try:
        result = await deepseek_client.analyze_card(
            text,
            model=ai_model,
            thinking=ai_thinking_enabled,
            reasoning_effort=ai_reasoning_effort,
        )
    except Exception:
        result = None
    if not result:
        return
    with SessionLocal() as db:
        card = db.get(Card, card_id)
        if not card:
            return
        if card.is_deleted or _content_fingerprint(card.plain_text) != expected_fingerprint:
            return
        card.sentiment = result["sentiment"]
        card.sentiment_confidence = result["confidence"]
        card.topic_labels = result["topics"]
        db.commit()
        db.refresh(card)
        card = db.scalar(
            select(Card)
            .where(Card.id == card_id)
            .options(selectinload(Card.author), selectinload(Card.reactions))
        )
        if not card:
            return
        public = card_to_public(card)
        wall_id = card.wall_id
    await manager.broadcast(wall_id, {"type": "card:sentiment", "payload": public})


@router.post("")
async def create_card(
    wall_id: str,
    payload: CardCreate,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    wall = _require_wall(db, wall_id, user, wall_access_token)
    _require_unlocked_for_member(wall, user)
    validated_text = _validate_content_or_422(payload.content_json, payload.plain_text)
    placeholder = placeholder_manager.consume(payload.placeholder_id, user.id)
    if placeholder and placeholder.wall_id == wall_id:
        x, y = placeholder.x, placeholder.y
    else:
        placed = _placed_cards(db, wall_id) + placeholder_manager.as_placed_cards(wall_id)
        x, y = find_nearest_legal(payload.x, payload.y, placed, payload.canvas_width)
    max_z = db.scalar(select(func.max(Card.z_index)).where(Card.wall_id == wall_id)) or 0
    card = Card(
        wall_id=wall_id,
        author_id=user.id,
        content_json=payload.content_json,
        plain_text=validated_text,
        x=x,
        y=y,
        color=payload.color or random.choice(COLORS),
        rotation=round(random.uniform(-4, 4), 1),
        z_index=max_z + 1,
    )
    if y + 260 > wall.canvas_height:
        wall.canvas_height = y + 650
    db.add(card)
    db.flush()
    log_action(db, wall_id, user.id, "card:create", {"card_id": card.id, "x": x, "y": y})
    db.commit()
    card = db.scalar(
        select(Card)
        .where(Card.id == card.id)
        .options(selectinload(Card.author), selectinload(Card.reactions))
    )
    public = card_to_public(card, user.id)
    if placeholder:
        await manager.broadcast(wall_id, {"type": "placeholder:remove", "payload": {"id": placeholder.id, "reason": "submitted"}})
    await manager.broadcast(wall_id, {"type": "card:create", "payload": public})
    asyncio.create_task(_analyze_later(card.id, _content_fingerprint(card.plain_text)))
    return public


@router.patch("/{card_id}")
async def update_card(
    wall_id: str,
    card_id: str,
    payload: CardUpdate,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_wall(db, wall_id, user, wall_access_token)
    card = db.scalar(select(Card).where(Card.id == card_id, Card.wall_id == wall_id).options(selectinload(Card.author), selectinload(Card.reactions)))
    if not card or card.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if card.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit this card")
    if payload.content_json is None and payload.plain_text is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No card changes provided")
    content_changed = payload.content_json is not None
    if payload.content_json is not None:
        validated_text = _validate_content_or_422(payload.content_json, payload.plain_text)
        card.content_json = payload.content_json
        card.plain_text = validated_text
        card.sentiment = None
        card.sentiment_confidence = None
        card.topic_labels = []
    elif payload.plain_text is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="content_json is required when changing plain_text")
    changed_fields = ["content_json", "plain_text"] if content_changed else []
    log_action(db, wall_id, user.id, "card:update", {"card_id": card_id, "fields": changed_fields})
    db.commit()
    db.refresh(card)
    public = card_to_public(card, user.id)
    await manager.broadcast(wall_id, {"type": "card:update", "payload": public})
    if content_changed:
        asyncio.create_task(_analyze_later(card.id, _content_fingerprint(card.plain_text)))
    return public


@router.post("/{card_id}/move")
async def move_card(
    wall_id: str,
    card_id: str,
    payload: CardMoveCommit,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    wall = _require_wall(db, wall_id, user, wall_access_token)
    _require_unlocked_for_member(wall, user)
    card = db.scalar(select(Card).where(Card.id == card_id, Card.wall_id == wall_id).options(selectinload(Card.author), selectinload(Card.reactions)))
    if not card or card.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if card.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot move this card")
    previous = {"x": card.x, "y": card.y}
    x, y = find_nearest_legal(payload.x, payload.y, _placed_cards(db, wall_id), payload.canvas_width, ignore_id=card.id)
    max_z = db.scalar(select(func.max(Card.z_index)).where(Card.wall_id == wall_id)) or 0
    card.x = x
    card.y = y
    card.z_index = max_z + 1
    if y + 260 > wall.canvas_height:
        wall.canvas_height = y + 650
    log_action(db, wall_id, user.id, "card:move", {"card_id": card_id, "from": previous, "to": {"x": x, "y": y}})
    db.commit()
    db.refresh(card)
    public = card_to_public(card, user.id)
    await manager.broadcast(wall_id, {"type": "card:move:commit", "payload": public})
    return public


@router.post("/{card_id}/reactions")
async def toggle_reaction(
    wall_id: str,
    card_id: str,
    payload: ReactionToggle,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_wall(db, wall_id, user, wall_access_token)
    card = db.scalar(select(Card).where(Card.id == card_id, Card.wall_id == wall_id).options(selectinload(Card.author), selectinload(Card.reactions)))
    if not card or card.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    user_reactions = db.scalars(
        select(Reaction).where(Reaction.card_id == card_id, Reaction.user_id == user.id)
    ).all()
    selected_types = set(REACTION_EQUIVALENTS[payload.reaction_type])
    already_selected = any(existing.reaction_type in selected_types for existing in user_reactions)
    for existing in user_reactions:
        db.delete(existing)
    if already_selected:
        state = "removed"
    else:
        db.add(Reaction(card_id=card_id, user_id=user.id, reaction_type=payload.reaction_type))
        state = "added"
    log_action(db, wall_id, user.id, "card:reaction", {"card_id": card_id, "reaction_type": payload.reaction_type, "state": state})
    db.commit()
    db.expire(card, ["reactions"])
    card = db.scalar(
        select(Card)
        .where(Card.id == card_id)
        .options(selectinload(Card.author), selectinload(Card.reactions))
        .execution_options(populate_existing=True)
    )
    public = card_to_public(card, user.id)
    await manager.broadcast(wall_id, {"type": "reaction:update", "payload": public})
    return public


@router.delete("/{card_id}", status_code=204)
async def delete_card(
    wall_id: str,
    card_id: str,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    wall = _require_wall(db, wall_id, user, wall_access_token)
    card = db.scalar(select(Card).where(Card.id == card_id, Card.wall_id == wall_id))
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if card.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete this card")
    card.is_deleted = True
    clear_spotlight = wall.spotlight_card_id == card_id
    if clear_spotlight:
        wall.spotlight_card_id = None
    action_type = "card:hide" if user.is_admin else "card:delete"
    log_action(db, wall_id, user.id, action_type, {"card_id": card_id})
    db.commit()
    await manager.broadcast(wall_id, {"type": "card:delete", "payload": {"card_id": card_id}})
    if clear_spotlight:
        await manager.broadcast(wall_id, {"type": "wall:spotlight", "payload": {"card_id": None}})
