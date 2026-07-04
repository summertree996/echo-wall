from pydantic import BaseModel, Field


class PlaceholderCreate(BaseModel):
    x: int
    y: int
    canvas_width: int = Field(default=1440, ge=720, le=3200)
    color_hint: str = "yellow"


class PlaceholderRenew(BaseModel):
    typing: bool = True


class PlaceholderPublic(BaseModel):
    id: str
    wall_id: str
    user_id: str
    user_name: str
    x: int
    y: int
    color_hint: str
    created_at: str
    expires_at: str
    last_activity_at: str

