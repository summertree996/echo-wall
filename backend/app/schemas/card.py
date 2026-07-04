from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CardCreate(BaseModel):
    content_json: dict[str, Any]
    plain_text: str = Field(min_length=1, max_length=150)
    x: int
    y: int
    canvas_width: int = Field(default=1440, ge=720, le=3200)
    color: str | None = None
    placeholder_id: str | None = None


class CardUpdate(BaseModel):
    content_json: dict[str, Any] | None = None
    plain_text: str | None = Field(default=None, min_length=1, max_length=150)


class CardMoveCommit(BaseModel):
    x: int
    y: int
    canvas_width: int = Field(default=1440, ge=720, le=3200)


class ReactionToggle(BaseModel):
    reaction_type: str = Field(pattern="^(like|dislike|question)$")


class CardPublic(BaseModel):
    id: str
    wall_id: str
    author_id: str
    author_name: str
    content_json: dict[str, Any]
    plain_text: str
    x: int
    y: int
    width: int
    height: int
    color: str
    rotation: float
    z_index: int
    sentiment: str | None
    sentiment_confidence: float | None
    topic_labels: list[str]
    reaction_counts: dict[str, int]
    own_reactions: list[str] = []
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class WallSnapshot(BaseModel):
    wall: dict[str, Any]
    cards: list[CardPublic]
    online_users: list[dict[str, Any]]
    placeholders: list[dict[str, Any]] = []
