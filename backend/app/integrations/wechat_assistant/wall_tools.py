from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import ActionLog, AiSummaryCache, Card, User, Wall
from app.services.serializers import reaction_counts, wall_to_public

from .models import WechatAssistantConnection
from .tooling import current_tool_context, tool


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _ctx_admin(db: Session) -> User:
    ctx = current_tool_context()
    user = db.get(User, ctx.source_user_id) if ctx and ctx.source_user_id else None
    if not user or not user.is_admin:
        raise PermissionError("admin_required")
    return user


def _current_connection(db: Session) -> WechatAssistantConnection | None:
    ctx = current_tool_context()
    connection_id = (ctx.source_metadata or {}).get("connection_id") if ctx else None
    if not connection_id:
        return None
    return db.get(WechatAssistantConnection, str(connection_id))


def _owned_wall(db: Session, wall_id: str | None) -> Wall:
    admin = _ctx_admin(db)
    if not wall_id:
        connection = _current_connection(db)
        wall_id = connection.current_wall_id if connection else None
    wall = db.get(Wall, wall_id) if wall_id else None
    if not wall or wall.owner_id != admin.id or wall.is_archived:
        raise LookupError("wall_not_found")
    return wall


def _set_current_wall(db: Session, wall: Wall) -> None:
    connection = _current_connection(db)
    if connection and connection.owner_user_id == wall.owner_id:
        connection.current_wall_id = wall.id
        db.add(connection)
        db.flush()


def _card_record(card: Card, wall: Wall) -> dict[str, Any]:
    counts = reaction_counts(card)
    return {
        "id": card.id,
        "text": card.plain_text,
        "author_name": "匿名成员" if wall.is_anonymous else card.author.nickname,
        "sentiment": card.sentiment or "unknown",
        "sentiment_confidence": card.sentiment_confidence,
        "topics": card.topic_labels or [],
        "reaction_counts": counts,
        "reaction_total": sum(counts.values()),
        "created_at": _iso(card.created_at),
        "updated_at": _iso(card.updated_at),
    }


def _wall_cards(db: Session, wall: Wall, limit: int = 1000) -> list[Card]:
    return list(
        db.scalars(
            select(Card)
            .where(Card.wall_id == wall.id, Card.is_deleted == False)  # noqa: E712
            .options(selectinload(Card.author), selectinload(Card.reactions))
            .order_by(Card.created_at.asc())
            .limit(limit)
        )
    )


@tool(
    name="list_my_walls",
    description="列出当前管理员拥有的反馈墙，用于帮助选择要讨论的墙。",
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def list_my_walls(_args: dict[str, Any], db: Session) -> dict[str, Any]:
    admin = _ctx_admin(db)
    rows = db.execute(
        select(Wall, func.count(Card.id))
        .outerjoin(Card, (Card.wall_id == Wall.id) & (Card.is_deleted == False))  # noqa: E712
        .where(Wall.owner_id == admin.id, Wall.is_archived == False)  # noqa: E712
        .group_by(Wall.id)
        .order_by(Wall.updated_at.desc())
        .limit(30)
    ).all()
    return {
        "walls": [
            {
                "id": wall.id,
                "title": wall.title,
                "description": wall.description,
                "access_mode": wall.access_mode,
                "card_count": int(card_count or 0),
                "is_anonymous": wall.is_anonymous,
                "ai_model": wall.ai_model,
                "thinking_enabled": wall.ai_thinking_enabled,
                "updated_at": _iso(wall.updated_at),
            }
            for wall, card_count in rows
        ]
    }


@tool(
    name="resolve_wall",
    description="根据墙标题、描述片段或墙 ID 匹配当前管理员拥有的反馈墙。匹配唯一时会把它设为当前对话墙。",
    parameters_schema={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "用户提到的墙名、墙 ID 或描述片段"}},
        "required": ["query"],
        "additionalProperties": False,
    },
)
def resolve_wall(args: dict[str, Any], db: Session) -> dict[str, Any]:
    admin = _ctx_admin(db)
    query = str(args.get("query") or "").strip()
    if not query:
        return {"matched": False, "reason": "empty_query", "candidates": list_my_walls({}, db)["walls"][:8]}
    candidates = list(
        db.scalars(
            select(Wall)
            .where(Wall.owner_id == admin.id, Wall.is_archived == False)  # noqa: E712
            .order_by(Wall.updated_at.desc())
        )
    )
    query_lower = query.lower()
    exact = [wall for wall in candidates if wall.id == query or wall.title.lower() == query_lower]
    contains = [
        wall
        for wall in candidates
        if wall not in exact and (query_lower in wall.title.lower() or query_lower in (wall.description or "").lower())
    ]
    matches = exact or contains
    if len(matches) == 1:
        wall = matches[0]
        _set_current_wall(db, wall)
        return {"matched": True, "wall": wall_to_public(wall)}
    return {
        "matched": False,
        "reason": "multiple_matches" if matches else "not_found",
        "candidates": [
            {"id": wall.id, "title": wall.title, "description": wall.description, "updated_at": _iso(wall.updated_at)}
            for wall in matches[:8] or candidates[:8]
        ],
    }


@tool(
    name="get_wall_brief",
    description="读取一面墙的基础统计、情绪分布、主题分布和反应概览。",
    parameters_schema={
        "type": "object",
        "properties": {"wall_id": {"type": "string", "description": "墙 ID；留空则使用当前对话墙"}},
        "additionalProperties": False,
    },
)
def get_wall_brief(args: dict[str, Any], db: Session) -> dict[str, Any]:
    wall = _owned_wall(db, args.get("wall_id"))
    cards = _wall_cards(db, wall)
    sentiment_counts = Counter(card.sentiment or "unknown" for card in cards)
    topic_counts = Counter(topic for card in cards for topic in (card.topic_labels or []))
    reaction_totals = Counter()
    for card in cards:
        reaction_totals.update(reaction_counts(card))
    return {
        "wall": wall_to_public(wall, len(cards)),
        "sentiment_counts": dict(sentiment_counts),
        "topic_counts": dict(topic_counts.most_common(20)),
        "reaction_totals": dict(reaction_totals),
        "latest_cards": [_card_record(card, wall) for card in cards[-8:]],
        "top_reacted_cards": [_card_record(card, wall) for card in sorted(cards, key=lambda item: sum(reaction_counts(item).values()), reverse=True)[:8]],
    }


@tool(
    name="get_wall_cards",
    description="读取一面墙的评论卡片全文、反应、情绪和主题。默认返回较完整数据。",
    parameters_schema={
        "type": "object",
        "properties": {
            "wall_id": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 1000},
        },
        "additionalProperties": False,
    },
)
def get_wall_cards(args: dict[str, Any], db: Session) -> dict[str, Any]:
    wall = _owned_wall(db, args.get("wall_id"))
    limit = max(1, min(int(args.get("limit") or 1000), 1000))
    cards = _wall_cards(db, wall, limit=limit)
    return {"wall": wall_to_public(wall, len(cards)), "cards": [_card_record(card, wall) for card in cards]}


@tool(
    name="search_wall_cards",
    description="按关键词、情绪或主题在当前管理员的某面墙中检索评论卡片。",
    parameters_schema={
        "type": "object",
        "properties": {
            "wall_id": {"type": "string"},
            "query": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative", "unknown", ""]},
            "topic": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30},
        },
        "additionalProperties": False,
    },
)
def search_wall_cards(args: dict[str, Any], db: Session) -> dict[str, Any]:
    wall = _owned_wall(db, args.get("wall_id"))
    query = str(args.get("query") or "").strip().lower()
    topic = str(args.get("topic") or "").strip().lower()
    sentiment = str(args.get("sentiment") or "").strip()
    limit = max(1, min(int(args.get("limit") or 30), 100))
    output: list[dict[str, Any]] = []
    for card in _wall_cards(db, wall, limit=1000):
        if sentiment and sentiment != "unknown" and card.sentiment != sentiment:
            continue
        if sentiment == "unknown" and card.sentiment:
            continue
        if query and query not in card.plain_text.lower():
            continue
        if topic and all(topic not in str(item).lower() for item in (card.topic_labels or [])):
            continue
        output.append(_card_record(card, wall))
        if len(output) >= limit:
            break
    return {"wall_id": wall.id, "matched": len(output), "cards": output}


@tool(
    name="get_wall_summary_history",
    description="读取一面墙已有的 AI 摘要历史，用于延续复盘和对比。",
    parameters_schema={
        "type": "object",
        "properties": {
            "wall_id": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "additionalProperties": False,
    },
)
def get_wall_summary_history(args: dict[str, Any], db: Session) -> dict[str, Any]:
    wall = _owned_wall(db, args.get("wall_id"))
    limit = max(1, min(int(args.get("limit") or 5), 10))
    rows = list(
        db.scalars(
            select(AiSummaryCache)
            .where(AiSummaryCache.wall_id == wall.id)
            .order_by(AiSummaryCache.generated_at.desc())
            .limit(limit)
        )
    )
    return {
        "wall_id": wall.id,
        "summaries": [
            {
                "id": item.id,
                "generated_at": _iso(item.generated_at),
                "model": item.model,
                "thinking_enabled": item.thinking_enabled,
                "reasoning_effort": item.reasoning_effort,
                "card_count": item.card_count,
                "payload": item.payload or {},
            }
            for item in rows
        ],
    }


@tool(
    name="prepare_wall_discussion_context",
    description="准备适合围绕某面反馈墙进行深入讨论的结构化上下文，包含全量评论、反应、情绪、主题、摘要和近期动作。",
    parameters_schema={
        "type": "object",
        "properties": {
            "wall_id": {"type": "string"},
            "include_actions": {"type": "boolean", "default": True},
            "max_cards": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 1000},
        },
        "additionalProperties": False,
    },
)
def prepare_wall_discussion_context(args: dict[str, Any], db: Session) -> dict[str, Any]:
    wall = _owned_wall(db, args.get("wall_id"))
    _set_current_wall(db, wall)
    max_cards = max(1, min(int(args.get("max_cards") or 1000), 1000))
    cards = _wall_cards(db, wall, limit=max_cards)
    brief = get_wall_brief({"wall_id": wall.id}, db)
    summaries = get_wall_summary_history({"wall_id": wall.id, "limit": 3}, db)["summaries"]
    actions: list[dict[str, Any]] = []
    if args.get("include_actions", True):
        rows = list(
            db.scalars(
                select(ActionLog)
                .where(ActionLog.wall_id == wall.id)
                .order_by(ActionLog.created_at.desc())
                .limit(80)
            )
        )
        actions = [
            {
                "id": item.id,
                "action_type": item.action_type,
                "payload": item.payload or {},
                "created_at": _iso(item.created_at),
            }
            for item in reversed(rows)
        ]
    return {
        "wall": wall_to_public(wall, len(cards)),
        "brief": brief,
        "cards": [_card_record(card, wall) for card in cards],
        "summary_history": summaries,
        "recent_actions": actions,
        "notes": {
            "anonymous_mode": wall.is_anonymous,
            "author_names_hidden": wall.is_anonymous,
            "card_count_returned": len(cards),
        },
    }
