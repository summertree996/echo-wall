from typing import Any

from sqlalchemy.orm import Session

from app.models import ActionLog


def log_action(
    db: Session,
    wall_id: str,
    user_id: str | None,
    action_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        ActionLog(
            wall_id=wall_id,
            user_id=user_id,
            action_type=action_type,
            payload=payload or {},
        )
    )
