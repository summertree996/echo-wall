from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResearchEventIn(BaseModel):
    client_session_id: str = Field(min_length=1, max_length=80)
    client_event_id: str | None = Field(default=None, max_length=96)
    event_type: str = Field(min_length=1, max_length=64)
    target_type: str | None = Field(default=None, max_length=32)
    target_id: str | None = Field(default=None, max_length=64)
    x: float | None = None
    y: float | None = None
    viewport_width: int | None = Field(default=None, ge=0, le=20000)
    viewport_height: int | None = Field(default=None, ge=0, le=20000)
    canvas_width: int | None = Field(default=None, ge=0, le=100000)
    canvas_height: int | None = Field(default=None, ge=0, le=100000)
    payload: dict[str, Any] = Field(default_factory=dict)
    client_ts: datetime | None = None


class ResearchEventBatch(BaseModel):
    events: list[ResearchEventIn] = Field(min_length=1, max_length=100)


class ResearchEventIngestResult(BaseModel):
    accepted: int


class ResearchUserSummary(BaseModel):
    actor_id: str
    user_id: str | None
    user_name: str
    email: str | None
    is_registered: bool
    client_session_ids: list[str]
    card_count: int
    reaction_count: int
    action_count: int
    research_event_count: int
    event_count: int
    event_counts: dict[str, int]
    sentiment_counts: dict[str, int]
    average_card_text_length: float
    first_seen: str | None
    last_seen: str | None
    active_span_seconds: float


class ResearchSummary(BaseModel):
    exported_at: str
    wall_id: str
    wall_title: str
    user_count: int
    event_count: int
    users: list[ResearchUserSummary]


class ResearchWallSnapshot(BaseModel):
    id: str
    title: str
    description: str
    canvas_width: int
    canvas_height: int


class ResearchDashboardMetrics(BaseModel):
    participants: int
    cards: int
    reactions: int
    action_events: int
    behavior_events: int
    total_events: int
    started_at: str | None
    ended_at: str | None
    active_span_seconds: float


class ResearchDashboardCard(BaseModel):
    id: str
    author_id: str
    author_name: str
    plain_text: str
    x: int
    y: int
    width: int
    height: int
    sentiment: str | None
    reaction_count: int
    created_at: str | None


class ResearchDashboardPoint(BaseModel):
    id: str
    user_id: str | None
    user_name: str
    event_type: str
    target_type: str | None
    target_id: str | None
    x: float
    y: float
    weight: float
    created_at: str | None


class ResearchTimelineEvent(BaseModel):
    id: str
    source: str
    user_id: str | None
    user_name: str
    event_type: str
    target_type: str | None
    target_id: str | None
    x: float | None
    y: float | None
    plain_text: str
    payload: dict[str, Any]
    created_at: str | None
    offset_seconds: float


class ResearchDashboard(BaseModel):
    exported_at: str
    wall: ResearchWallSnapshot
    metrics: ResearchDashboardMetrics
    users: list[ResearchUserSummary]
    cards: list[ResearchDashboardCard]
    heatmap_points: list[ResearchDashboardPoint]
    timeline: list[ResearchTimelineEvent]
    event_rows: list[ResearchTimelineEvent]
