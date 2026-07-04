from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceCard(BaseModel):
    id: str
    text: str
    sentiment: str | None = None
    reaction_count: int = 0


class SummaryPoint(BaseModel):
    title: str
    summary: str
    evidence: list[EvidenceCard] = Field(default_factory=list)


class RiskPoint(BaseModel):
    title: str
    severity: str
    summary: str
    evidence: list[EvidenceCard] = Field(default_factory=list)


class WallSummaryPublic(BaseModel):
    summary_id: str | None = None
    generated_at: datetime
    model: str
    thinking_enabled: bool
    reasoning_effort: str = "high"
    cached: bool = False
    cache_key: str | None = None
    card_count: int = 0
    overview: str
    sentiment_counts: dict[str, int]
    key_points: list[SummaryPoint]
    risks: list[RiskPoint]
    representative_cards: list[EvidenceCard]


class WallSummaryHistoryItem(BaseModel):
    id: str
    generated_at: datetime
    model: str
    thinking_enabled: bool
    reasoning_effort: str
    card_count: int
    cache_key: str
    overview: str = ""


class WallSummaryDiffPublic(BaseModel):
    summary_id: str
    against_id: str
    generated_at: datetime
    against_generated_at: datetime
    card_count_delta: int
    sentiment_delta: dict[str, int]
    key_points_added: list[str] = Field(default_factory=list)
    key_points_removed: list[str] = Field(default_factory=list)
    risks_added: list[str] = Field(default_factory=list)
    risks_removed: list[str] = Field(default_factory=list)
    representative_cards_added: list[str] = Field(default_factory=list)
    representative_cards_removed: list[str] = Field(default_factory=list)
    overview_changed: bool = False
