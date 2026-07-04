from pydantic import BaseModel, Field


class IntegrationRequirementPublic(BaseModel):
    title: str
    detail: str


class IntegrationStatusPublic(BaseModel):
    key: str
    label: str
    status: str
    enabled: bool
    message: str
    planned_endpoint: str | None = None
    requirements: list[IntegrationRequirementPublic] = Field(default_factory=list)
