from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db import SessionLocal
from app.models import Card, User, Wall
from app.services.serializers import card_to_public, wall_to_public
from app.services.placeholders import placeholder_manager
from app.services.wall_access import has_wall_access
from app.websocket.manager import manager


router = APIRouter(tags=["websocket"])


def _tokens_from_subprotocols(websocket: WebSocket) -> tuple[str | None, str | None, str | None]:
    token = None
    wall_access_token = None
    accepted_subprotocol = None
    raw_protocols = websocket.headers.get("sec-websocket-protocol", "")
    for item in raw_protocols.split(","):
        protocol = item.strip()
        if protocol == "talon":
            accepted_subprotocol = "talon"
        if protocol.startswith("talon.auth."):
            token = protocol.removeprefix("talon.auth.")
        if protocol.startswith("talon.wall."):
            wall_access_token = protocol.removeprefix("talon.wall.")
    return token, wall_access_token, accepted_subprotocol


@router.websocket("/ws/walls/{wall_id}")
async def wall_socket(
    websocket: WebSocket,
    wall_id: str,
    token: str | None = None,
    wall_access_token: str | None = None,
) -> None:
    protocol_token, protocol_wall_access_token, accepted_subprotocol = _tokens_from_subprotocols(websocket)
    token = protocol_token or token
    wall_access_token = protocol_wall_access_token or wall_access_token
    with SessionLocal() as db:
        user = None
        if token:
            try:
                payload = decode_access_token(token)
                user = db.get(User, payload.get("sub"))
            except InvalidTokenError:
                user = None
        wall = db.get(Wall, wall_id)
        if not wall or wall.is_archived:
            await websocket.close(code=4404)
            return
        if wall.access_mode == "login_required" and not user:
            await websocket.close(code=4401)
            return
        if wall.access_mode == "password_required" and not has_wall_access(wall, wall_access_token, user):
            await websocket.close(code=4403)
            return
        identity = {"id": user.id if user else "guest", "nickname": user.nickname if user else "访客"}

    await manager.connect(wall_id, websocket, identity, subprotocol=accepted_subprotocol)
    try:
        with SessionLocal() as db:
            wall = db.get(Wall, wall_id)
            cards = db.scalars(
                select(Card)
                .where(Card.wall_id == wall_id, Card.is_deleted == False)  # noqa: E712
                .options(selectinload(Card.author), selectinload(Card.reactions))
            ).all()
            await websocket.send_json(
                {
                    "type": "wall:snapshot",
                    "payload": {
                        "wall": wall_to_public(wall, len(cards)),
                        "cards": [card_to_public(card, user.id if user else None) for card in cards],
                        "online_users": manager.online_users(wall_id),
                        "placeholders": [item.to_public() for item in placeholder_manager.active_for_wall(wall_id)],
                    },
                }
            )
        await manager.broadcast(wall_id, {"type": "presence:update", "payload": manager.online_users(wall_id)})
        while True:
            event = await websocket.receive_json()
            if event.get("type") == "card:move:transient":
                await manager.broadcast(wall_id, event, exclude=websocket)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(wall_id, websocket)
        if user and not manager.has_user(wall_id, user.id):
            released = placeholder_manager.release_for_user(wall_id, user.id)
            for item in released:
                await manager.broadcast(wall_id, {"type": "placeholder:remove", "payload": {"id": item.id, "reason": "disconnected"}})
        await manager.broadcast(wall_id, {"type": "presence:update", "payload": manager.online_users(wall_id)})
