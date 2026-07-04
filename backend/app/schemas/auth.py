from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    nickname: str
    is_admin: bool

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class AuthEventPublic(BaseModel):
    id: str
    user_id: str | None = None
    email: EmailStr
    event_type: str
    ip_address: str = ""
    user_agent: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}
