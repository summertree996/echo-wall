import csv
import io
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_optional_user, get_wall_access_token, require_admin
from app.core.security import hash_password
from app.db import get_db
from app.models import ActionLog, Card, User, Wall
from app.schemas.wall import WallAccessRequest, WallAccessResponse, WallCreate, WallPublic, WallSpotlightRequest, WallUpdate
from app.services.action_log import log_action
from app.services.serializers import card_to_public, wall_to_public
from app.services.placeholders import placeholder_manager
from app.services.wall_access import create_wall_access_token, has_wall_access, verify_wall_password
from app.websocket.manager import manager


router = APIRouter(prefix="/walls", tags=["walls"])


def _action_to_public(action: ActionLog, user_names: dict[str, str]) -> dict:
    return {
        "id": action.id,
        "wall_id": action.wall_id,
        "user_id": action.user_id,
        "user_name": user_names.get(action.user_id or "", ""),
        "action_type": action.action_type,
        "payload": action.payload or {},
        "created_at": action.created_at.isoformat() if action.created_at else "",
    }


@router.get("/admin", response_model=list[WallPublic])
def list_admin_walls(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Wall, func.count(Card.id))
        .outerjoin(Card, (Card.wall_id == Wall.id) & (Card.is_deleted == False))  # noqa: E712
        .where(Wall.owner_id == admin.id)
        .group_by(Wall.id)
        .order_by(Wall.updated_at.desc())
    ).all()
    return [wall_to_public(wall, count) for wall, count in rows]


@router.post("", response_model=WallPublic)
def create_wall(payload: WallCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if payload.access_mode == "password_required" and not payload.password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password is required for password walls")
    wall = Wall(
        title=payload.title,
        description=payload.description,
        access_mode=payload.access_mode,
        password_hash=hash_password(payload.password) if payload.password else None,
        ai_enabled=payload.ai_enabled,
        ai_model=payload.ai_model,
        ai_thinking_enabled=payload.ai_thinking_enabled,
        ai_reasoning_effort=payload.ai_reasoning_effort,
        owner_id=admin.id,
    )
    db.add(wall)
    db.flush()
    log_action(db, wall.id, admin.id, "wall:create", {"access_mode": wall.access_mode})
    db.commit()
    db.refresh(wall)
    return wall_to_public(wall)


@router.get("/{wall_id}/export")
def export_wall(wall_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    wall = db.get(Wall, wall_id)
    if not wall or wall.owner_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    cards = db.scalars(
        select(Card)
        .where(Card.wall_id == wall_id, Card.is_deleted == False)  # noqa: E712
        .options(selectinload(Card.author), selectinload(Card.reactions))
        .order_by(Card.created_at.asc())
    ).all()
    log_action(db, wall_id, admin.id, "wall:export_json", {"card_count": len(cards)})
    db.commit()
    actions = db.scalars(select(ActionLog).where(ActionLog.wall_id == wall_id).order_by(ActionLog.created_at.asc())).all()
    user_ids = {action.user_id for action in actions if action.user_id}
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_names = {user.id: user.nickname for user in users}
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "wall": wall_to_public(wall, len(cards)),
        "counts": {
            "cards": len(cards),
            "positive": sum(1 for card in cards if card.sentiment == "positive"),
            "neutral": sum(1 for card in cards if card.sentiment == "neutral" or card.sentiment is None),
            "negative": sum(1 for card in cards if card.sentiment == "negative"),
        },
        "cards": [card_to_public(card) for card in cards],
        "actions": [_action_to_public(action, user_names) for action in actions],
    }


@router.get("/{wall_id}/export.csv")
def export_wall_csv(wall_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    wall = db.get(Wall, wall_id)
    if not wall or wall.owner_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    cards = db.scalars(
        select(Card)
        .where(Card.wall_id == wall_id, Card.is_deleted == False)  # noqa: E712
        .options(selectinload(Card.author), selectinload(Card.reactions))
        .order_by(Card.created_at.asc())
    ).all()
    log_action(db, wall_id, admin.id, "wall:export_csv", {"card_count": len(cards)})
    db.commit()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "author_name",
            "plain_text",
            "sentiment",
            "topics",
            "like",
            "dislike",
            "question",
            "created_at",
            "updated_at",
        ],
    )
    writer.writeheader()
    for card in cards:
        counts = card_to_public(card)["reaction_counts"]
        writer.writerow(
            {
                "id": card.id,
                "author_name": "匿名成员" if wall.is_anonymous else card.author.nickname,
                "plain_text": card.plain_text,
                "sentiment": card.sentiment or "",
                "topics": ";".join(card.topic_labels or []),
                "like": counts["like"],
                "dislike": counts["dislike"],
                "question": counts["question"],
                "created_at": card.created_at.isoformat() if card.created_at else "",
                "updated_at": card.updated_at.isoformat() if card.updated_at else "",
            }
        )
    output.seek(0)
    filename = f"{wall.id}-cards.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{wall_id}/export.actions.csv")
def export_wall_actions_csv(wall_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    wall = db.get(Wall, wall_id)
    if not wall or wall.owner_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    log_action(db, wall_id, admin.id, "wall:export_actions_csv", {})
    db.commit()

    actions = db.scalars(select(ActionLog).where(ActionLog.wall_id == wall_id).order_by(ActionLog.created_at.asc())).all()
    user_ids = {action.user_id for action in actions if action.user_id}
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_names = {user.id: user.nickname for user in users}

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "user_id",
            "user_name",
            "action_type",
            "payload_json",
            "created_at",
        ],
    )
    writer.writeheader()
    for action in actions:
        writer.writerow(
            {
                "id": action.id,
                "user_id": action.user_id or "",
                "user_name": user_names.get(action.user_id or "", ""),
                "action_type": action.action_type,
                "payload_json": json.dumps(action.payload or {}, ensure_ascii=False, sort_keys=True),
                "created_at": action.created_at.isoformat() if action.created_at else "",
            }
        )
    output.seek(0)
    filename = f"{wall.id}-actions.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{wall_id}/spotlight")
async def set_wall_spotlight(
    wall_id: str,
    payload: WallSpotlightRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    wall = db.get(Wall, wall_id)
    if not wall or wall.owner_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    if payload.card_id:
        card = db.scalar(select(Card).where(Card.id == payload.card_id, Card.wall_id == wall_id, Card.is_deleted == False))  # noqa: E712
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    wall.spotlight_card_id = payload.card_id
    log_action(db, wall_id, admin.id, "wall:spotlight", {"card_id": payload.card_id})
    db.commit()
    public = {"card_id": payload.card_id}
    await manager.broadcast(wall_id, {"type": "wall:spotlight", "payload": public})
    return public


@router.post("/{wall_id}/access", response_model=WallAccessResponse)
def unlock_wall(
    wall_id: str,
    payload: WallAccessRequest,
    db: Session = Depends(get_db),
) -> dict:
    wall = db.get(Wall, wall_id)
    if not wall or wall.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    if wall.access_mode != "password_required":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wall does not require a password")
    if not verify_wall_password(wall, payload.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid wall password")
    return {"wall_access_token": create_wall_access_token(wall_id)}


@router.get("/{wall_id}")
def get_wall(
    wall_id: str,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> dict:
    wall = db.get(Wall, wall_id)
    if not wall or wall.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    if wall.access_mode == "password_required" and not has_wall_access(wall, wall_access_token, user):
        return {"wall": wall_to_public(wall), "requires_password": True, "cards": []}
    if wall.access_mode == "login_required" and not user:
        return {"wall": wall_to_public(wall), "requires_login": True, "cards": []}
    cards = db.scalars(
        select(Card)
        .where(Card.wall_id == wall_id, Card.is_deleted == False)  # noqa: E712
        .options(selectinload(Card.author), selectinload(Card.reactions))
        .order_by(Card.z_index.asc(), Card.created_at.asc())
    ).all()
    return {
        "wall": wall_to_public(wall, len(cards)),
        "cards": [card_to_public(card, user.id if user else None) for card in cards],
        "online_users": manager.online_users(wall_id),
        "placeholders": [item.to_public() for item in placeholder_manager.active_for_wall(wall_id)],
    }


@router.patch("/{wall_id}", response_model=WallPublic)
async def update_wall(
    wall_id: str,
    payload: WallUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    wall = db.get(Wall, wall_id)
    if not wall or wall.owner_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    changes = payload.model_dump(exclude_unset=True)
    new_password = changes.pop("password", None)
    if new_password:
        wall.password_hash = hash_password(new_password)
    next_access_mode = changes.get("access_mode", wall.access_mode)
    if next_access_mode == "password_required" and not wall.password_hash:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password is required for password walls")
    for field, value in changes.items():
        setattr(wall, field, value)
    log_payload = {"fields": sorted(changes.keys())}
    if new_password:
        log_payload["password_updated"] = True
    log_action(db, wall_id, admin.id, "wall:update", log_payload)
    db.commit()
    db.refresh(wall)
    card_count = db.scalar(select(func.count(Card.id)).where(Card.wall_id == wall_id, Card.is_deleted == False)) or 0  # noqa: E712
    public = wall_to_public(wall, card_count)
    await manager.broadcast(wall_id, {"type": "wall:update", "payload": public})
    return public
