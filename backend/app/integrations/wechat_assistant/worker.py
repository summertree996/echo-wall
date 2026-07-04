from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal

from .ai_gateway import AgentReply, generate_agent_reply
from .crypto import protect_secret, reveal_secret
from .models import (
    WechatAssistantConnection,
    WechatAssistantContextToken,
    WechatAssistantDeliveryLog,
    WechatAssistantInboundMessage,
    WechatAssistantOutboundMessage,
)
from .provider import InboundUpdate, WechatAssistantProvider


ONBOARDING_TEXT = (
    "ECHO 微信助手已连接。\n\n"
    "你可以问我：\n"
    "- 某面墙大家主要在说什么\n"
    "- 负面反馈集中在哪里\n"
    "- 哪些评论适合现场讨论\n"
    "- 帮我整理主持回应或会后复盘\n\n"
    "收到，我正在读取反馈墙信息。"
)
THINKING_ACK_TEXT = "收到，我正在读取反馈墙信息。"
HEARTBEAT_TEXTS = ("还在整理评论和互动数据，稍等我一下。", "这面墙的信息有点多，我还在归纳，完成后会直接回复你。")
HEARTBEAT_DELAYS_SECONDS = (30, 60)
MAX_WORKERS = 10

_POOL = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="talon-wechat-ai")
_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT_CONNECTIONS: dict[str, str] = {}


def _bot_token(connection: WechatAssistantConnection) -> str:
    return reveal_secret(connection.bot_token_secret) or ""


def _save_context_token(db: Session, *, connection_id: str, external_user_id: str, token: str) -> None:
    db.query(WechatAssistantContextToken).filter(
        WechatAssistantContextToken.connection_id == connection_id,
        WechatAssistantContextToken.external_user_id != external_user_id,
    ).delete(synchronize_session=False)
    row = db.query(WechatAssistantContextToken).filter(
        WechatAssistantContextToken.connection_id == connection_id,
        WechatAssistantContextToken.external_user_id == external_user_id,
    ).first()
    secret = protect_secret(token) or ""
    if row:
        row.context_token_secret = secret
    else:
        db.add(
            WechatAssistantContextToken(
                connection_id=connection_id,
                external_user_id=external_user_id,
                context_token_secret=secret,
            )
        )


def _send_text_outbound(
    db: Session,
    *,
    connection: WechatAssistantConnection,
    provider: WechatAssistantProvider,
    external_user_id: str,
    text: str | None,
    context_token: str | None,
    reply_to_inbound_id: str | None,
    delivery_policy: str,
) -> WechatAssistantOutboundMessage:
    outbound = WechatAssistantOutboundMessage(
        connection_id=connection.id,
        reply_to_inbound_id=reply_to_inbound_id,
        external_user_id=external_user_id,
        text_content=text,
        delivery_policy=delivery_policy,
        context_token_present=bool(context_token),
        delivery_status="pending",
    )
    db.add(outbound)
    db.flush()
    if not context_token:
        outbound.delivery_status = "failed"
        outbound.delivery_reason = "context_token_missing"
        db.add(
            WechatAssistantDeliveryLog(
                connection_id=connection.id,
                outbound_message_id=outbound.id,
                action="send",
                ok=False,
                error_message="context_token_missing",
            )
        )
        return outbound
    result = provider.send_message(
        bot_token=_bot_token(connection),
        external_user_id=external_user_id,
        text=text,
        context_token=context_token,
    )
    outbound.delivery_status = "sent" if result.ok else "failed"
    outbound.delivery_reason = None if result.ok else result.reason
    outbound.provider_message_id = result.provider_message_id
    db.add(
        WechatAssistantDeliveryLog(
            connection_id=connection.id,
            outbound_message_id=outbound.id,
            action="send",
            ok=result.ok,
            error_message=None if result.ok else result.reason,
        )
    )
    return outbound


def send_manual_text(
    db: Session,
    *,
    connection: WechatAssistantConnection,
    provider: WechatAssistantProvider,
    text: str,
    external_user_id: str | None = None,
) -> WechatAssistantOutboundMessage:
    recipient = external_user_id
    if not recipient:
        context_rows = (
            db.query(WechatAssistantContextToken)
            .filter(WechatAssistantContextToken.connection_id == connection.id)
            .order_by(WechatAssistantContextToken.updated_at.desc())
            .all()
        )
        for context_row in context_rows:
            if not context_row.external_user_id.startswith("admin-"):
                recipient = context_row.external_user_id
                break
    if not recipient:
        raise ValueError("wechat_context_missing")
    context_row = (
        db.query(WechatAssistantContextToken)
        .filter(
            WechatAssistantContextToken.connection_id == connection.id,
            WechatAssistantContextToken.external_user_id == recipient,
        )
        .first()
    )
    context_token = reveal_secret(context_row.context_token_secret) if context_row else None
    if not context_token:
        raise ValueError("wechat_context_missing")
    return _send_text_outbound(
        db,
        connection=connection,
        provider=provider,
        external_user_id=recipient,
        text=text,
        context_token=context_token,
        reply_to_inbound_id=None,
        delivery_policy="manual_test",
    )


def _has_sent_onboarding(db: Session, connection_id: str) -> bool:
    return (
        db.query(WechatAssistantOutboundMessage.id)
        .filter(
            WechatAssistantOutboundMessage.connection_id == connection_id,
            WechatAssistantOutboundMessage.delivery_policy == "onboarding",
            WechatAssistantOutboundMessage.delivery_status == "sent",
        )
        .first()
        is not None
    )


def _send_initial_feedback(
    db: Session,
    *,
    connection: WechatAssistantConnection,
    inbound: WechatAssistantInboundMessage,
    update: InboundUpdate,
    provider: WechatAssistantProvider,
    context_token: str | None,
) -> None:
    if not context_token:
        return
    if not _has_sent_onboarding(db, connection.id):
        _send_text_outbound(
            db,
            connection=connection,
            provider=provider,
            external_user_id=update.external_user_id,
            text=ONBOARDING_TEXT,
            context_token=context_token,
            reply_to_inbound_id=inbound.id,
            delivery_policy="onboarding",
        )
        return
    _send_text_outbound(
        db,
        connection=connection,
        provider=provider,
        external_user_id=update.external_user_id,
        text=THINKING_ACK_TEXT,
        context_token=context_token,
        reply_to_inbound_id=inbound.id,
        delivery_policy="thinking",
    )


def _start_heartbeat(
    *,
    connection: WechatAssistantConnection,
    external_user_id: str,
    context_token: str | None,
    provider: WechatAssistantProvider,
    done_event: threading.Event,
) -> None:
    if not context_token:
        return
    bot_token = _bot_token(connection)
    if not bot_token:
        return

    def _runner() -> None:
        for delay, text in zip(HEARTBEAT_DELAYS_SECONDS, HEARTBEAT_TEXTS):
            if done_event.wait(delay):
                return
            db = SessionLocal()
            try:
                connection_row = db.get(WechatAssistantConnection, connection.id)
                if connection_row is None:
                    return
                _send_text_outbound(
                    db,
                    connection=connection_row,
                    provider=provider,
                    external_user_id=external_user_id,
                    text=text,
                    context_token=context_token,
                    reply_to_inbound_id=None,
                    delivery_policy="thinking",
                )
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()

    threading.Thread(target=_runner, name=f"talon-wechat-heartbeat-{connection.id}", daemon=True).start()


def _mark_inflight(connection_id: str, inbound_id: str) -> None:
    with _INFLIGHT_LOCK:
        _INFLIGHT_CONNECTIONS[connection_id] = inbound_id


def _clear_inflight(connection_id: str, inbound_id: str) -> None:
    with _INFLIGHT_LOCK:
        if _INFLIGHT_CONNECTIONS.get(connection_id) == inbound_id:
            _INFLIGHT_CONNECTIONS.pop(connection_id, None)


def _busy_inbound_id(connection_id: str) -> str | None:
    with _INFLIGHT_LOCK:
        return _INFLIGHT_CONNECTIONS.get(connection_id)


def _busy_reply(inbound_id: str) -> AgentReply:
    return AgentReply(
        text="我还在处理你上一条消息，请稍等。处理完后我会直接回复你。",
        delivery_policy="reply",
        metadata={"mode": "busy", "busy_inbound_id": inbound_id},
    )


def _apply_reply(
    db: Session,
    *,
    connection: WechatAssistantConnection,
    inbound: WechatAssistantInboundMessage,
    external_user_id: str,
    context_token: str | None,
    provider: WechatAssistantProvider,
    reply: AgentReply,
) -> None:
    inbound.ai_metadata = reply.metadata
    outbound = _send_text_outbound(
        db,
        connection=connection,
        provider=provider,
        external_user_id=external_user_id,
        text=reply.text,
        context_token=context_token,
        reply_to_inbound_id=inbound.id,
        delivery_policy=reply.delivery_policy,
    )
    inbound.agent_reply_id = outbound.id
    inbound.processed_at = datetime.now(UTC).replace(tzinfo=None)
    db.flush()


def _run_reply_job(
    *,
    connection_id: str,
    inbound_id: str,
    external_user_id: str,
    context_token: str | None,
    provider: WechatAssistantProvider,
) -> None:
    done_event = threading.Event()
    db = SessionLocal()
    try:
        connection = db.get(WechatAssistantConnection, connection_id)
        inbound = db.get(WechatAssistantInboundMessage, inbound_id)
        if not connection or not inbound:
            return
        _start_heartbeat(
            connection=connection,
            external_user_id=external_user_id,
            context_token=context_token,
            provider=provider,
            done_event=done_event,
        )
        reply = generate_agent_reply(
            db=db,
            connection=connection,
            inbound=inbound,
            bound=bool(connection.owner_user_id and connection.status == "connected"),
        )
        _apply_reply(
            db,
            connection=connection,
            inbound=inbound,
            external_user_id=external_user_id,
            context_token=context_token,
            provider=provider,
            reply=reply,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        try:
            connection = db.get(WechatAssistantConnection, connection_id)
            inbound = db.get(WechatAssistantInboundMessage, inbound_id)
            if connection and inbound:
                _apply_reply(
                    db,
                    connection=connection,
                    inbound=inbound,
                    external_user_id=external_user_id,
                    context_token=context_token,
                    provider=provider,
                    reply=AgentReply(
                        text=f"暂时无法完成这次反馈墙查询，请稍后再试。（{type(exc).__name__}）",
                        delivery_policy="reply",
                        metadata={"mode": "job_error", "error_type": type(exc).__name__},
                    ),
                )
                db.commit()
        except Exception:
            db.rollback()
    finally:
        done_event.set()
        db.close()
        _clear_inflight(connection_id, inbound_id)


def process_update(
    db: Session,
    *,
    connection: WechatAssistantConnection,
    update: InboundUpdate,
    provider: WechatAssistantProvider,
    defer_agent_reply: bool = True,
) -> WechatAssistantInboundMessage:
    existing = (
        db.query(WechatAssistantInboundMessage)
        .filter(
            WechatAssistantInboundMessage.connection_id == connection.id,
            WechatAssistantInboundMessage.external_message_id == update.external_message_id,
        )
        .first()
    )
    if existing:
        return existing
    if update.context_token:
        _save_context_token(
            db,
            connection_id=connection.id,
            external_user_id=update.external_user_id,
            token=update.context_token,
        )
    inbound = WechatAssistantInboundMessage(
        connection_id=connection.id,
        external_message_id=update.external_message_id,
        external_user_id=update.external_user_id,
        owner_user_id=connection.owner_user_id if connection.status == "connected" else None,
        message_type=update.message_type,
        text_content=update.text_content,
        raw_payload_json=update.raw or None,
    )
    db.add(inbound)
    db.flush()
    context_token = update.context_token or None
    _send_initial_feedback(
        db,
        connection=connection,
        inbound=inbound,
        update=update,
        provider=provider,
        context_token=context_token,
    )
    busy_id = _busy_inbound_id(connection.id)
    if busy_id and (inbound.text_content or "").strip():
        _apply_reply(
            db,
            connection=connection,
            inbound=inbound,
            external_user_id=update.external_user_id,
            context_token=context_token,
            provider=provider,
            reply=_busy_reply(busy_id),
        )
        return inbound
    if defer_agent_reply:
        db.commit()
        _mark_inflight(connection.id, inbound.id)
        _POOL.submit(
            _run_reply_job,
            connection_id=connection.id,
            inbound_id=inbound.id,
            external_user_id=update.external_user_id,
            context_token=context_token,
            provider=provider,
        )
        return inbound
    done_event = threading.Event()
    _start_heartbeat(
        connection=connection,
        external_user_id=update.external_user_id,
        context_token=context_token,
        provider=provider,
        done_event=done_event,
    )
    try:
        reply = generate_agent_reply(
            db=db,
            connection=connection,
            inbound=inbound,
            bound=bool(connection.owner_user_id and connection.status == "connected"),
        )
    finally:
        done_event.set()
    _apply_reply(
        db,
        connection=connection,
        inbound=inbound,
        external_user_id=update.external_user_id,
        context_token=context_token,
        provider=provider,
        reply=reply,
    )
    return inbound


def poll_connection(
    db: Session,
    *,
    connection: WechatAssistantConnection,
    provider,
    defer_agent_reply: bool = True,
) -> list[WechatAssistantInboundMessage]:
    token = _bot_token(connection)
    updates, cursor = provider.get_updates(token, connection.last_cursor)
    processed: list[WechatAssistantInboundMessage] = []
    for update in updates:
        processed.append(
            process_update(
                db,
                connection=connection,
                update=update,
                provider=provider,
                defer_agent_reply=defer_agent_reply,
            )
        )
    connection.last_cursor = cursor
    db.add(connection)
    db.flush()
    return processed
