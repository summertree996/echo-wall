from pydantic import BaseModel

from app.schemas.wall import AiModel, AiReasoningEffort


class AiConnectionTestRequest(BaseModel):
    ai_model: AiModel | None = None
    ai_thinking_enabled: bool | None = None
    ai_reasoning_effort: AiReasoningEffort | None = None


class AiConnectionTestPublic(BaseModel):
    status: str
    model: str
    thinking_enabled: bool
    reasoning_effort: str
    latency_ms: int
    message: str
