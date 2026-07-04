from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db import get_db
from app.models import User, Wall

from .crypto import protect_secret
from .background import wechat_assistant_background
from .models import (
    WechatAssistantConnection,
    WechatAssistantContextToken,
    WechatAssistantInboundMessage,
    WechatAssistantOutboundMessage,
)
from .provider import MockWechatAssistantProvider, get_provider, provider_status
from .ai_gateway import generate_agent_reply
from .worker import poll_connection, send_manual_text


router = APIRouter(prefix="/wechat-assistant", tags=["wechat-assistant"])


class PollQRCodeRequest(BaseModel):
    connection_id: str


class TestAiQueryRequest(BaseModel):
    text: str
    wall_id: str | None = None


class TestSendRequest(BaseModel):
    text: str
    external_user_id: str | None = None


class CurrentWallRequest(BaseModel):
    wall_id: str | None = None


def _connection_to_public(connection: WechatAssistantConnection) -> dict[str, Any]:
    return {
        "id": connection.id,
        "owner_user_id": connection.owner_user_id,
        "provider": connection.provider,
        "status": connection.status,
        "status_reason": connection.status_reason,
        "provider_account_id": connection.provider_account_id,
        "base_url": connection.base_url,
        "last_cursor": connection.last_cursor,
        "current_wall_id": connection.current_wall_id,
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
    }


def _owned_connection(db: Session, connection_id: str, admin: User) -> WechatAssistantConnection:
    connection = db.get(WechatAssistantConnection, connection_id)
    if not connection or connection.owner_user_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return connection


@router.get("/status")
def wechat_assistant_status(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    total = db.scalar(
        select(func.count(WechatAssistantConnection.id)).where(WechatAssistantConnection.owner_user_id == admin.id)
    ) or 0
    connected = db.scalar(
        select(func.count(WechatAssistantConnection.id)).where(
            WechatAssistantConnection.owner_user_id == admin.id,
            WechatAssistantConnection.status == "connected",
        )
    ) or 0
    latest = db.scalar(
        select(WechatAssistantConnection)
        .where(WechatAssistantConnection.owner_user_id == admin.id)
        .order_by(WechatAssistantConnection.updated_at.desc())
    )
    return {
        "key": "wechat_assistant",
        "label": "AI 微信助手",
        "enabled": connected > 0,
        "status": "connected" if connected else "available",
        "message": "管理员可以通过微信私聊查询和讨论反馈墙数据。",
        "provider": provider_status(),
        "worker": wechat_assistant_background.status(),
        "connection_count": int(total),
        "connected_count": int(connected),
        "latest_connection": _connection_to_public(latest) if latest else None,
        "capabilities": [
            "二维码连接",
            "微信私聊查询",
            "反馈墙全量上下文讨论",
            "评论检索和归类",
            "摘要历史读取",
            "thinking 和 heartbeat 反馈",
        ],
        "guardrails": [
            "只读取和讨论反馈墙数据",
            "不删除用户、卡片或墙",
            "不改权限",
            "不控制画布",
        ],
    }


@router.get("/connections")
def list_connections(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(WechatAssistantConnection)
            .where(WechatAssistantConnection.owner_user_id == admin.id)
            .order_by(WechatAssistantConnection.updated_at.desc())
        )
    )
    return [_connection_to_public(row) for row in rows]


@router.post("/connections/request-qrcode")
def request_qrcode(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        result = get_provider().request_qrcode()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"微信二维码申请失败：{type(exc).__name__}",
        ) from exc
    if not result.qrcode_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="微信二维码申请失败：服务没有返回二维码图片",
        )
    connection = WechatAssistantConnection(
        owner_user_id=admin.id,
        provider="wechat_clawbot",
        status="pending_qrcode",
        qrcode_session=result.session,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return {
        "connection_id": connection.id,
        "status": connection.status,
        "qrcode_url": result.qrcode_url,
    }


@router.post("/connections/poll-qrcode-status")
def poll_qrcode_status(
    payload: PollQRCodeRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    connection = _owned_connection(db, payload.connection_id, admin)
    if connection.status == "connected":
        return _connection_to_public(connection)
    if connection.status != "pending_qrcode":
        return _connection_to_public(connection)
    result = get_provider().poll_qrcode(connection.qrcode_session or "")
    normalized_status = result.status
    if result.status in {"confirmed", "success", "connected", "done"} and result.bot_token:
        old_rows = list(
            db.scalars(
                select(WechatAssistantConnection).where(
                    WechatAssistantConnection.owner_user_id == admin.id,
                    WechatAssistantConnection.id != connection.id,
                    WechatAssistantConnection.status == "connected",
                )
            )
        )
        for old in old_rows:
            old.status = "disconnected"
            old.status_reason = "replaced_by_new_connection"
            db.query(WechatAssistantContextToken).filter(WechatAssistantContextToken.connection_id == old.id).delete(
                synchronize_session=False
            )
        connection.status = "connected"
        connection.status_reason = None
        connection.bot_token_secret = protect_secret(result.bot_token)
        connection.provider_account_id = result.provider_account_id
        connection.base_url = result.base_url
        normalized_status = "connected"
    elif result.status in {"expired", "error"}:
        connection.status = result.status
        connection.status_reason = result.reason
    else:
        connection.status_reason = result.reason
    db.add(connection)
    db.commit()
    db.refresh(connection)
    public = _connection_to_public(connection)
    public["provider_status"] = normalized_status
    return public


@router.post("/connections/{connection_id}/mock-confirm")
def mock_confirm_connection(
    connection_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    connection = _owned_connection(db, connection_id, admin)
    provider = get_provider()
    if not isinstance(provider, MockWechatAssistantProvider):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mock provider is not active")
    if connection.status != "pending_qrcode":
        return _connection_to_public(connection)
    result_token = provider.confirm(connection.qrcode_session or "", provider_account_id="mock-admin-bot")
    connection.status = "connected"
    connection.status_reason = None
    connection.bot_token_secret = protect_secret(result_token)
    connection.provider_account_id = "mock-admin-bot"
    connection.base_url = "https://mock.local"
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _connection_to_public(connection)


@router.patch("/connections/{connection_id}/current-wall")
def set_current_wall(
    connection_id: str,
    payload: CurrentWallRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    connection = _owned_connection(db, connection_id, admin)
    if payload.wall_id:
        wall = db.get(Wall, payload.wall_id)
        if not wall or wall.owner_id != admin.id or wall.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
        connection.current_wall_id = wall.id
    else:
        connection.current_wall_id = None
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _connection_to_public(connection)


@router.delete("/connections/{connection_id}", status_code=204, response_model=None)
def disconnect_connection(
    connection_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    connection = _owned_connection(db, connection_id, admin)
    connection.status = "disconnected"
    connection.status_reason = "disconnected_by_admin"
    db.query(WechatAssistantContextToken).filter(WechatAssistantContextToken.connection_id == connection.id).delete(
        synchronize_session=False
    )
    db.commit()


@router.post("/connections/{connection_id}/poll-once")
def poll_once(
    connection_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    connection = _owned_connection(db, connection_id, admin)
    if connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection is not connected")
    processed = poll_connection(db, connection=connection, provider=get_provider(), defer_agent_reply=True)
    db.commit()
    return {"processed": len(processed), "inbound_ids": [item.id for item in processed]}


@router.post("/connections/{connection_id}/test-ai-query")
def test_ai_query(
    connection_id: str,
    payload: TestAiQueryRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    connection = _owned_connection(db, connection_id, admin)
    if connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection is not connected")
    if payload.wall_id:
        wall = db.get(Wall, payload.wall_id)
        if not wall or wall.owner_id != admin.id or wall.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
        connection.current_wall_id = payload.wall_id
        db.add(connection)
        db.flush()
    inbound = WechatAssistantInboundMessage(
        connection_id=connection.id,
        external_message_id=f"test-{datetime.now(UTC).timestamp()}",
        external_user_id="admin-local-test",
        owner_user_id=admin.id,
        message_type="text",
        text_content=payload.text,
        raw_payload_json={"source": "test-ai-query"},
    )
    db.add(inbound)
    db.flush()
    reply = generate_agent_reply(
        db=db,
        connection=connection,
        inbound=inbound,
        bound=True,
    )
    inbound.ai_metadata = reply.metadata
    inbound.processed_at = datetime.now(UTC).replace(tzinfo=None)
    outbound = WechatAssistantOutboundMessage(
        connection_id=connection.id,
        reply_to_inbound_id=inbound.id,
        external_user_id=inbound.external_user_id,
        text_content=reply.text,
        delivery_policy="local_test",
        context_token_present=False,
        delivery_status="local_only",
    )
    db.add(outbound)
    db.flush()
    inbound.agent_reply_id = outbound.id
    db.commit()
    return {
        "inbound_id": inbound.id,
        "reply": outbound.text_content if outbound else None,
        "metadata": inbound.ai_metadata,
    }


@router.post("/connections/{connection_id}/test-send")
def test_send(
    connection_id: str,
    payload: TestSendRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    connection = _owned_connection(db, connection_id, admin)
    if connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection is not connected")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message text is required")
    try:
        outbound = send_manual_text(
            db,
            connection=connection,
            provider=get_provider(),
            text=text,
            external_user_id=payload.external_user_id,
        )
    except ValueError as exc:
        if str(exc) == "wechat_context_missing":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前连接还没有可下推的微信会话，请先从微信侧发一条消息。",
            ) from exc
        raise
    db.commit()
    db.refresh(outbound)
    return {
        "outbound_id": outbound.id,
        "external_user_id": outbound.external_user_id,
        "delivery_status": outbound.delivery_status,
        "delivery_reason": outbound.delivery_reason,
        "provider_message_id": outbound.provider_message_id,
    }


@router.get("/messages/inbox")
def inbox(
    limit: int = 30,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    rows = list(
        db.scalars(
            select(WechatAssistantInboundMessage)
            .join(WechatAssistantConnection, WechatAssistantConnection.id == WechatAssistantInboundMessage.connection_id)
            .where(WechatAssistantConnection.owner_user_id == admin.id)
            .order_by(WechatAssistantInboundMessage.received_at.desc())
            .limit(limit)
        )
    )
    outbound_ids = [row.agent_reply_id for row in rows if row.agent_reply_id]
    outbounds = {
        row.id: row
        for row in db.scalars(select(WechatAssistantOutboundMessage).where(WechatAssistantOutboundMessage.id.in_(outbound_ids))).all()
    } if outbound_ids else {}
    return [
        {
            "id": row.id,
            "connection_id": row.connection_id,
            "external_message_id": row.external_message_id,
            "message_type": row.message_type,
            "text_content": row.text_content,
            "received_at": row.received_at,
            "processed_at": row.processed_at,
            "ai_metadata": row.ai_metadata,
            "reply": outbounds[row.agent_reply_id].text_content if row.agent_reply_id in outbounds else None,
        }
        for row in rows
    ]


@router.get("/messages/timeline")
def timeline(
    connection_id: str | None = None,
    limit: int = 80,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    connection_filter = [WechatAssistantConnection.owner_user_id == admin.id]
    if connection_id:
        connection_filter.append(WechatAssistantConnection.id == connection_id)
    inbound_rows = list(
        db.scalars(
            select(WechatAssistantInboundMessage)
            .join(WechatAssistantConnection, WechatAssistantConnection.id == WechatAssistantInboundMessage.connection_id)
            .where(*connection_filter)
            .order_by(WechatAssistantInboundMessage.received_at.desc())
            .limit(limit)
        )
    )
    outbound_rows = list(
        db.scalars(
            select(WechatAssistantOutboundMessage)
            .join(WechatAssistantConnection, WechatAssistantConnection.id == WechatAssistantOutboundMessage.connection_id)
            .where(*connection_filter)
            .order_by(WechatAssistantOutboundMessage.created_at.desc())
            .limit(limit)
        )
    )
    items: list[dict[str, Any]] = []
    for row in inbound_rows:
        items.append(
            {
                "id": row.id,
                "direction": "inbound",
                "connection_id": row.connection_id,
                "external_user_id": row.external_user_id,
                "message_type": row.message_type,
                "text_content": row.text_content,
                "delivery_policy": None,
                "delivery_status": "received" if row.processed_at is None else "processed",
                "delivery_reason": None,
                "related_inbound_id": None,
                "ai_metadata": row.ai_metadata,
                "timestamp": row.received_at,
            }
        )
    for row in outbound_rows:
        items.append(
            {
                "id": row.id,
                "direction": "outbound",
                "connection_id": row.connection_id,
                "external_user_id": row.external_user_id,
                "message_type": "text",
                "text_content": row.text_content,
                "delivery_policy": row.delivery_policy,
                "delivery_status": row.delivery_status,
                "delivery_reason": row.delivery_reason,
                "related_inbound_id": row.reply_to_inbound_id,
                "ai_metadata": None,
                "timestamp": row.created_at,
            }
        )
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return items[:limit]
