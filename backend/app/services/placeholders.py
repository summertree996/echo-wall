from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.placement import PlacedCard


PLACEHOLDER_TTL_SECONDS = 90


@dataclass
class Placeholder:
    id: str
    wall_id: str
    user_id: str
    user_name: str
    x: int
    y: int
    color_hint: str
    created_at: datetime
    expires_at: datetime
    last_activity_at: datetime

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "wall_id": self.wall_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "x": self.x,
            "y": self.y,
            "color_hint": self.color_hint,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
        }


class PlaceholderManager:
    def __init__(self) -> None:
        self._items: dict[str, Placeholder] = {}

    def cleanup(self) -> list[Placeholder]:
        now = self._now()
        expired = [item for item in self._items.values() if item.expires_at <= now]
        for item in expired:
            self._items.pop(item.id, None)
        return expired

    def active_for_wall(self, wall_id: str, exclude_id: str | None = None) -> list[Placeholder]:
        self.cleanup()
        return [
            item
            for item in self._items.values()
            if item.wall_id == wall_id and (exclude_id is None or item.id != exclude_id)
        ]

    def as_placed_cards(self, wall_id: str, exclude_id: str | None = None) -> list[PlacedCard]:
        return [PlacedCard(id=item.id, x=item.x, y=item.y) for item in self.active_for_wall(wall_id, exclude_id)]

    def create(
        self,
        wall_id: str,
        user_id: str,
        user_name: str,
        x: int,
        y: int,
        color_hint: str,
    ) -> tuple[Placeholder, list[Placeholder]]:
        self.cleanup()
        replaced = [
            item for item in self._items.values() if item.wall_id == wall_id and item.user_id == user_id
        ]
        for item in replaced:
            self._items.pop(item.id, None)

        now = self._now()
        item = Placeholder(
            id=f"ph_{uuid4().hex[:12]}",
            wall_id=wall_id,
            user_id=user_id,
            user_name=user_name,
            x=x,
            y=y,
            color_hint=color_hint,
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(seconds=PLACEHOLDER_TTL_SECONDS),
        )
        self._items[item.id] = item
        return item, replaced

    def renew(self, placeholder_id: str, user_id: str) -> Placeholder | None:
        self.cleanup()
        item = self._items.get(placeholder_id)
        if not item or item.user_id != user_id:
            return None
        now = self._now()
        item.last_activity_at = now
        item.expires_at = now + timedelta(seconds=PLACEHOLDER_TTL_SECONDS)
        return item

    def release(self, placeholder_id: str, user_id: str | None = None) -> Placeholder | None:
        self.cleanup()
        item = self._items.get(placeholder_id)
        if not item:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return self._items.pop(placeholder_id, None)

    def release_for_user(self, wall_id: str, user_id: str) -> list[Placeholder]:
        self.cleanup()
        released = [
            item for item in self._items.values() if item.wall_id == wall_id and item.user_id == user_id
        ]
        for item in released:
            self._items.pop(item.id, None)
        return released

    def consume(self, placeholder_id: str | None, user_id: str) -> Placeholder | None:
        if not placeholder_id:
            return None
        return self.release(placeholder_id, user_id=user_id)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)


placeholder_manager = PlaceholderManager()
