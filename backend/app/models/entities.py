from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("u"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cards: Mapped[list["Card"]] = relationship(back_populates="author")


class Wall(Base):
    __tablename__ = "walls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("w"))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    access_mode: Mapped[str] = mapped_column(String(32), default="login_required")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canvas_height: Mapped[int] = mapped_column(Integer, default=2400)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    spotlight_card_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_model: Mapped[str] = mapped_column(String(64), default="deepseek-v4-flash")
    ai_thinking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_reasoning_effort: Mapped[str] = mapped_column(String(16), default="high")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped[User] = relationship()
    cards: Mapped[list["Card"]] = relationship(back_populates="wall", cascade="all, delete-orphan")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("c"))
    wall_id: Mapped[str] = mapped_column(ForeignKey("walls.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    content_json: Mapped[dict] = mapped_column(JSON)
    plain_text: Mapped[str] = mapped_column(Text)
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer, default=250)
    height: Mapped[int] = mapped_column(Integer, default=170)
    color: Mapped[str] = mapped_column(String(32))
    rotation: Mapped[float] = mapped_column(Float, default=0)
    z_index: Mapped[int] = mapped_column(Integer, default=1)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic_labels: Mapped[list] = mapped_column(JSON, default=list)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    wall: Mapped[Wall] = relationship(back_populates="cards")
    author: Mapped[User] = relationship(back_populates="cards")
    reactions: Mapped[list["Reaction"]] = relationship(back_populates="card", cascade="all, delete-orphan")


class Reaction(Base):
    __tablename__ = "reactions"
    __table_args__ = (UniqueConstraint("card_id", "user_id", "reaction_type", name="uq_reaction_once"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("r"))
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reaction_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    card: Mapped[Card] = relationship(back_populates="reactions")
    user: Mapped[User] = relationship()


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("a"))
    wall_id: Mapped[str] = mapped_column(ForeignKey("walls.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ResearchEvent(Base):
    __tablename__ = "research_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ev"))
    wall_id: Mapped[str] = mapped_column(ForeignKey("walls.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    client_session_id: Mapped[str] = mapped_column(String(80), index=True)
    client_event_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)
    viewport_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    viewport_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canvas_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canvas_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    client_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class AuthEvent(Base):
    __tablename__ = "auth_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ae"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AiSummaryCache(Base):
    __tablename__ = "ai_summary_caches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("sum"))
    wall_id: Mapped[str] = mapped_column(ForeignKey("walls.id"), index=True)
    cache_key: Mapped[str] = mapped_column(String(128), index=True)
    model: Mapped[str] = mapped_column(String(64))
    thinking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reasoning_effort: Mapped[str] = mapped_column(String(16), default="high")
    card_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
