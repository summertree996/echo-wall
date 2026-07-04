from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_wall_access_token
from app.db import get_db
from app.models import Card, User, Wall
from app.schemas.placeholder import PlaceholderCreate, PlaceholderPublic, PlaceholderRenew
from app.services.placeholders import placeholder_manager
from app.services.placement import PlacedCard, find_nearest_legal
from app.services.wall_access import has_wall_access
from app.websocket.manager import manager


router = APIRouter(prefix="/walls/{wall_id}/placeholders", tags=["placeholders"])


def _wall_or_404(db: Session, wall_id: str, user: User | None = None, wall_access_token: str | None = None) -> Wall:
    wall = db.get(Wall, wall_id)
    if not wall or wall.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    if not has_wall_access(wall, wall_access_token, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wall password required")
    return wall


def _placed_cards(db: Session, wall_id: str) -> list[PlacedCard]:
    cards = db.scalars(select(Card).where(Card.wall_id == wall_id, Card.is_deleted == False)).all()  # noqa: E712
    return [PlacedCard(id=card.id, x=card.x, y=card.y, width=card.width, height=card.height) for card in cards]


@router.post("", response_model=PlaceholderPublic)
async def create_placeholder(
    wall_id: str,
    payload: PlaceholderCreate,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    wall = _wall_or_404(db, wall_id, user, wall_access_token)
    if wall.is_locked and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wall is locked")
    other_placeholders = [
        PlacedCard(id=item.id, x=item.x, y=item.y)
        for item in placeholder_manager.active_for_wall(wall_id)
        if item.user_id != user.id
    ]
    existing_cards = _placed_cards(db, wall_id) + other_placeholders
    x, y = find_nearest_legal(payload.x, payload.y, existing_cards, payload.canvas_width)
    item, replaced = placeholder_manager.create(
        wall_id=wall_id,
        user_id=user.id,
        user_name=user.nickname,
        x=x,
        y=y,
        color_hint=payload.color_hint,
    )
    for old in replaced:
        await manager.broadcast(wall_id, {"type": "placeholder:remove", "payload": {"id": old.id, "reason": "replaced"}})
    public = item.to_public()
    await manager.broadcast(wall_id, {"type": "placeholder:create", "payload": public})
    return public


@router.patch("/{placeholder_id}", response_model=PlaceholderPublic)
async def renew_placeholder(
    wall_id: str,
    placeholder_id: str,
    _payload: PlaceholderRenew,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _wall_or_404(db, wall_id, user, wall_access_token)
    item = placeholder_manager.renew(placeholder_id, user.id)
    if not item or item.wall_id != wall_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placeholder not found")
    public = item.to_public()
    await manager.broadcast(wall_id, {"type": "placeholder:renew", "payload": public})
    return public


@router.delete("/{placeholder_id}", status_code=204)
async def release_placeholder(
    wall_id: str,
    placeholder_id: str,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _wall_or_404(db, wall_id, user, wall_access_token)
    item = placeholder_manager.release(placeholder_id, user.id)
    if item:
        await manager.broadcast(wall_id, {"type": "placeholder:remove", "payload": {"id": item.id, "reason": "cancelled"}})
    return Response(status_code=204)
