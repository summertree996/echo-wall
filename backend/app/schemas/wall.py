from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AccessMode = Literal["link_only", "login_required", "password_required"]
AiModel = Literal["deepseek-v4-flash", "deepseek-v4-pro"]
AiReasoningEffort = Literal["high", "max"]


class WallCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = ""
    access_mode: AccessMode = "login_required"
    password: str | None = Field(default=None, min_length=1, max_length=80)
    ai_enabled: bool = True
    ai_model: AiModel = "deepseek-v4-flash"
    ai_thinking_enabled: bool = False
    ai_reasoning_effort: AiReasoningEffort = "high"


class WallUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    access_mode: AccessMode | None = None
    password: str | None = Field(default=None, min_length=1, max_length=80)
    is_anonymous: bool | None = None
    is_archived: bool | None = None
    is_locked: bool | None = None
    ai_enabled: bool | None = None
    ai_model: AiModel | None = None
    ai_thinking_enabled: bool | None = None
    ai_reasoning_effort: AiReasoningEffort | None = None


class WallPublic(BaseModel):
    id: str
    title: str
    description: str
    access_mode: str
    has_password: bool
    canvas_height: int
    is_anonymous: bool
    is_archived: bool
    is_locked: bool
    spotlight_card_id: str | None = None
    ai_enabled: bool
    ai_model: str
    ai_thinking_enabled: bool
    ai_reasoning_effort: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    card_count: int = 0

    model_config = {"from_attributes": True}


class WallAccessRequest(BaseModel):
    password: str = Field(min_length=1, max_length=80)


class WallAccessResponse(BaseModel):
    wall_access_token: str
    token_type: str = "wall_access"


class WallSpotlightRequest(BaseModel):
    card_id: str | None = None
