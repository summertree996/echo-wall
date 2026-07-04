from jwt import InvalidTokenError

from app.core.security import create_access_token, decode_access_token, verify_password
from app.models import User, Wall


WALL_ACCESS_PURPOSE = "wall_access"


def create_wall_access_token(wall_id: str) -> str:
    return create_access_token(wall_id, {"purpose": WALL_ACCESS_PURPOSE})


def has_wall_access(wall: Wall, wall_access_token: str | None, user: User | None = None) -> bool:
    if wall.access_mode != "password_required":
        return True
    if user and (user.is_admin or user.id == wall.owner_id):
        return True
    if not wall_access_token:
        return False
    try:
        payload = decode_access_token(wall_access_token)
    except InvalidTokenError:
        return False
    return payload.get("purpose") == WALL_ACCESS_PURPOSE and payload.get("sub") == wall.id


def verify_wall_password(wall: Wall, password: str) -> bool:
    return bool(wall.password_hash and verify_password(password, wall.password_hash))
