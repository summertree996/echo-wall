from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CheckStatus = Literal["ok", "warning", "error"]


class SystemCheckPublic(BaseModel):
    key: str
    label: str
    status: CheckStatus
    detail: str


class SystemStatusPublic(BaseModel):
    status: CheckStatus
    checked_at: datetime
    checks: list[SystemCheckPublic] = Field(default_factory=list)
