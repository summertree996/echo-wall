from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.entities import new_id


class WechatAssistantConnection(Base):
    __tablename__ = "wechat_assistant_connections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wac"))
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="wechat_clawbot")
    status: Mapped[str] = mapped_column(String(32), default="pending_qrcode")
    status_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    bot_token_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_cursor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    qrcode_session: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_wall_id: Mapped[str | None] = mapped_column(ForeignKey("walls.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class WechatAssistantContextToken(Base):
    __tablename__ = "wechat_assistant_context_tokens"
    __table_args__ = (
        UniqueConstraint("connection_id", "external_user_id", name="uq_wechat_assistant_ctx"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wct"))
    connection_id: Mapped[str] = mapped_column(ForeignKey("wechat_assistant_connections.id"), index=True)
    external_user_id: Mapped[str] = mapped_column(String(128))
    context_token_secret: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class WechatAssistantInboundMessage(Base):
    __tablename__ = "wechat_assistant_inbound_messages"
    __table_args__ = (
        UniqueConstraint("connection_id", "external_message_id", name="uq_wechat_assistant_inbound_ext"),
        Index("ix_wechat_assistant_inbound_processed", "processed_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wai"))
    connection_id: Mapped[str] = mapped_column(ForeignKey("wechat_assistant_connections.id"), index=True)
    external_message_id: Mapped[str] = mapped_column(String(128))
    external_user_id: Mapped[str] = mapped_column(String(128))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    message_type: Mapped[str] = mapped_column(String(32), default="text")
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ai_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    agent_reply_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class WechatAssistantOutboundMessage(Base):
    __tablename__ = "wechat_assistant_outbound_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wao"))
    connection_id: Mapped[str] = mapped_column(ForeignKey("wechat_assistant_connections.id"), index=True)
    reply_to_inbound_id: Mapped[str | None] = mapped_column(
        ForeignKey("wechat_assistant_inbound_messages.id"),
        nullable=True,
    )
    external_user_id: Mapped[str] = mapped_column(String(128))
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_policy: Mapped[str] = mapped_column(String(32), default="reply")
    context_token_present: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_status: Mapped[str] = mapped_column(String(32), default="pending")
    delivery_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class WechatAssistantDeliveryLog(Base):
    __tablename__ = "wechat_assistant_delivery_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wad"))
    connection_id: Mapped[str] = mapped_column(ForeignKey("wechat_assistant_connections.id"), index=True)
    outbound_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("wechat_assistant_outbound_messages.id"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(32))
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
