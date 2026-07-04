from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Wall

from . import wall_tools  # noqa: F401  ensure tool registration
from .models import (
    WechatAssistantConnection,
    WechatAssistantInboundMessage,
    WechatAssistantOutboundMessage,
)
from .tool_loop import DeepSeekToolLoop
from .tooling import ToolRunContext, get_tools


_SIMPLE_GREETINGS = {"你好", "您好", "hi", "hello", "hey", "在吗", "哈喽"}

ASSISTANT_TOOL_NAMES = [
    "list_my_walls",
    "resolve_wall",
    "get_wall_brief",
    "get_wall_cards",
    "search_wall_cards",
    "get_wall_summary_history",
    "prepare_wall_discussion_context",
]

HISTORY_EXCLUDED_PREFIXES = (
    "ECHO 微信助手已连接",
    "收到，我正在读取反馈墙信息",
    "还在整理评论和互动数据",
    "我还在处理你上一条消息",
    "这条消息没有可用文字",
)

_MARKDOWN_BULLET_RE = re.compile(r"^\s*[-*+]\s+")
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*")
_MARKDOWN_ORDERED_RE = re.compile(r"^\s*(\d+)[.)]\s+")


@dataclass
class AgentReply:
    text: str
    delivery_policy: str
    metadata: dict[str, Any]


def _wall_guess_from_text(db: Session, connection: WechatAssistantConnection, text: str) -> Wall | None:
    text_lower = text.lower()
    walls = list(
        db.scalars(
            select(Wall)
            .where(Wall.owner_id == connection.owner_user_id, Wall.is_archived == False)  # noqa: E712
            .order_by(Wall.updated_at.desc())
        )
    )
    for wall in walls:
        if wall.id in text or wall.title.lower() in text_lower:
            connection.current_wall_id = wall.id
            db.add(connection)
            db.flush()
            return wall
    if connection.current_wall_id:
        current = db.get(Wall, connection.current_wall_id)
        if current and current.owner_id == connection.owner_user_id and not current.is_archived:
            return current
    return None


def build_history_context(
    db: Session,
    *,
    owner_user_id: str | None,
    exclude_inbound_id: str | None,
    max_pairs: int = 5,
    max_age_hours: int = 24,
    max_chars_per_message: int = 900,
) -> str:
    if not owner_user_id:
        return ""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=max_age_hours)
    query = (
        select(WechatAssistantInboundMessage)
        .where(
            WechatAssistantInboundMessage.owner_user_id == owner_user_id,
            WechatAssistantInboundMessage.received_at >= cutoff,
            WechatAssistantInboundMessage.text_content.is_not(None),
        )
        .order_by(WechatAssistantInboundMessage.received_at.desc())
        .limit(max_pairs * 4)
    )
    if exclude_inbound_id:
        query = query.where(WechatAssistantInboundMessage.id != exclude_inbound_id)
    inbounds = list(db.scalars(query))
    if not inbounds:
        return ""
    inbound_ids = [item.id for item in inbounds]
    outbounds = list(
        db.scalars(
            select(WechatAssistantOutboundMessage).where(
                WechatAssistantOutboundMessage.reply_to_inbound_id.in_(inbound_ids),
                WechatAssistantOutboundMessage.delivery_policy == "reply",
                WechatAssistantOutboundMessage.delivery_status.in_(("sent", "degraded")),
            )
        )
    )
    reply_by_inbound = {item.reply_to_inbound_id: item.text_content for item in outbounds if item.text_content}
    pairs: list[str] = []
    for inbound in reversed(inbounds):
        user_text = (inbound.text_content or "").strip()[:max_chars_per_message]
        assistant_text = (reply_by_inbound.get(inbound.id) or "").strip()[:max_chars_per_message]
        if not user_text or not assistant_text:
            continue
        if any(assistant_text.startswith(prefix) for prefix in HISTORY_EXCLUDED_PREFIXES):
            continue
        pairs.append(f"用户：{user_text}\n助手：{assistant_text}")
    pairs = pairs[-max_pairs:]
    if not pairs:
        return ""
    return "\n\n最近对话历史：\n" + "\n---\n".join(pairs)


def build_instructions(db: Session, *, connection: WechatAssistantConnection, current_wall: Wall | None) -> str:
    history = build_history_context(
        db,
        owner_user_id=connection.owner_user_id,
        exclude_inbound_id=None,
    )
    current_wall_block = ""
    if current_wall:
        current_wall_block = (
            f"\n当前对话墙：{current_wall.title}，ID={current_wall.id}。"
            "用户没明确指定墙时，优先围绕当前对话墙回答。"
        )
    return (
        "你是 ECHO 的管理员微信助手。管理员会在微信里询问反馈墙情况，"
        "你要通过工具读取墙、评论、反应、情绪、主题和摘要历史，然后进行讨论、总结、归类和主持建议。\n\n"
        "工作边界：\n"
        "1. 默认只查询和讨论，不执行删除、归档、改权限、控制画布、删除用户等动作。\n"
        "2. 当用户问某面墙时，先用 resolve_wall 或 list_my_walls 确定目标墙。匹配不唯一时只问一个澄清问题。\n"
        "3. 针对一面墙深入讨论时，优先调用 prepare_wall_discussion_context 获取完整结构化上下文。\n"
        "4. 可以基于全量评论、反应、情绪、主题、摘要历史和近期动作提出观察、风险点、代表评论和主持回应建议。\n"
        "5. 不要编造评论内容、卡片 ID 或统计数据；没有查到就直接说明。\n"
        "6. 匿名模式开启时，不要暴露真实作者名。\n"
        "7. 最终回复面向微信手机竖屏阅读，用纯文本短段落、空行、少量 emoji 和 3 到 6 条要点即可。\n"
        "8. 最终回复不要使用 Markdown 标题、粗体、代码块、引用块、表格或 JSON，不要输出 #、**、```、| 表格线。\n"
        "9. 调用工具时，参数必须是合法 JSON 对象，不要包 Markdown 代码块，不要把 JSON 再编码成字符串。\n"
        "10. 可以给管理员生成可复制的复盘草稿、主持提示、回应话术，但只作为建议文本返回。\n"
        f"{current_wall_block}"
        f"{history}"
    )


def format_wechat_reply_text(text: str) -> str:
    lines: list[str] = []
    in_code_fence = False
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if not in_code_fence:
            line = _MARKDOWN_HEADING_RE.sub("", line)
            line = _MARKDOWN_BULLET_RE.sub("· ", line)
            line = _MARKDOWN_ORDERED_RE.sub(r"\1. ", line)
            line = line.removeprefix("> ").removeprefix(">")
            line = line.replace("**", "").replace("__", "").replace("`", "")
        lines.append(line)
    output = "\n".join(lines).strip()
    while "\n\n\n" in output:
        output = output.replace("\n\n\n", "\n\n")
    return output


def _fallback_reply(error_type: str) -> str:
    if error_type == "deepseek_key_missing":
        return "DeepSeek key 还没有配置好，暂时不能完成微信侧 AI 查询。"
    return f"暂时无法完成这次反馈墙查询。可能是 AI 服务或工具调用临时不可用，请稍后再试。（{error_type}）"


def run_wall_assistant_query(
    db: Session,
    *,
    connection: WechatAssistantConnection,
    inbound: WechatAssistantInboundMessage,
) -> AgentReply:
    text = (inbound.text_content or "").strip()
    if not text:
        return AgentReply(
            text="这条消息没有可用文字。请直接发文字描述你想查询哪面墙或哪个问题。",
            delivery_policy="reply",
            metadata={"mode": "empty_text"},
        )
    if text.lower() in _SIMPLE_GREETINGS:
        return AgentReply(
            text="我在。你可以直接问某面反馈墙的主要观点、负面反馈、代表评论或复盘建议。",
            delivery_policy="reply",
            metadata={"mode": "simple_greeting"},
        )
    current_wall = _wall_guess_from_text(db, connection, text)
    settings = get_settings()
    model = current_wall.ai_model if current_wall else settings.deepseek_default_model
    thinking = current_wall.ai_thinking_enabled if current_wall else settings.deepseek_default_thinking
    effort = current_wall.ai_reasoning_effort if current_wall else "high"
    loop = DeepSeekToolLoop(
        model=model,
        thinking=thinking,
        reasoning_effort=effort,
        max_turns=6,
        max_output_tokens=5000,
        temperature=0.2,
    )
    try:
        result = loop.run(
            user_text=text,
            instructions=build_instructions(db, connection=connection, current_wall=current_wall),
            tools=get_tools(ASSISTANT_TOOL_NAMES),
            context=ToolRunContext(
                source_user_id=connection.owner_user_id,
                source_type="wechat",
                source_metadata={
                    "connection_id": connection.id,
                    "inbound_id": inbound.id,
                    "external_user_id": inbound.external_user_id,
                    "current_wall_id": connection.current_wall_id,
                },
            ),
            db=db,
        )
    except Exception as exc:  # noqa: BLE001
        return AgentReply(
            text=_fallback_reply(type(exc).__name__),
            delivery_policy="reply",
            metadata={"mode": "ai_error", "error_type": type(exc).__name__, "error_message": str(exc)[:500]},
        )
    output = format_wechat_reply_text((result.final_text or "").strip()) or _fallback_reply("empty_output")
    return AgentReply(
        text=output,
        delivery_policy="reply",
        metadata={
            "mode": "ai_loop",
            "status": result.status,
            "model": model,
            "thinking_enabled": thinking,
            "reasoning_effort": effort,
            "tool_calls": [record.__dict__ for record in result.tool_calls],
            "error_message": result.error_message,
            "raw_usage": result.raw_usage,
        },
    )


def generate_agent_reply(
    *,
    db: Session,
    connection: WechatAssistantConnection,
    inbound: WechatAssistantInboundMessage,
    bound: bool,
) -> AgentReply:
    if not bound:
        return AgentReply(
            text="请先在管理台完成微信助手连接后再继续使用。",
            delivery_policy="reply",
            metadata={"mode": "unbound"},
        )
    return run_wall_assistant_query(db, connection=connection, inbound=inbound)
