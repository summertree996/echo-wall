import csv
import io
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_optional_user, get_wall_access_token, require_admin
from app.db import get_db
from app.models import ActionLog, Card, Reaction, ResearchEvent, User, Wall
from app.schemas.research import ResearchDashboard, ResearchEventBatch, ResearchEventIngestResult, ResearchSummary
from app.services.action_log import log_action
from app.services.serializers import reaction_counts
from app.services.wall_access import has_wall_access


router = APIRouter(prefix="/walls/{wall_id}/research", tags=["research"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_wall_for_event(
    db: Session,
    wall_id: str,
    user: User | None,
    wall_access_token: str | None,
) -> Wall:
    wall = db.get(Wall, wall_id)
    if not wall or wall.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    if wall.access_mode == "login_required" and not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    if not has_wall_access(wall, wall_access_token, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wall password required")
    return wall


def _require_owned_wall(db: Session, wall_id: str, admin: User) -> Wall:
    wall = db.get(Wall, wall_id)
    if not wall or wall.owner_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    return wall


def _actor_key(user_id: str | None, session_id: str | None = None) -> str:
    if user_id:
        return f"user:{user_id}"
    return f"session:{session_id or 'unknown'}"


def _empty_summary(actor_id: str, user: User | None = None, session_id: str | None = None) -> dict[str, Any]:
    is_registered = user is not None
    return {
        "actor_id": actor_id,
        "user_id": user.id if user else None,
        "user_name": user.nickname if user else f"访客会话 {actor_id[-6:]}",
        "email": user.email if user else None,
        "is_registered": is_registered,
        "client_session_ids": set([session_id] if session_id else []),
        "card_count": 0,
        "reaction_count": 0,
        "action_count": 0,
        "research_event_count": 0,
        "event_count": 0,
        "event_counts": Counter(),
        "sentiment_counts": Counter(),
        "text_lengths": [],
        "first_seen": None,
        "last_seen": None,
    }


def _touch(summary: dict[str, Any], created_at: datetime | None) -> None:
    if not created_at:
        return
    if summary["first_seen"] is None or created_at < summary["first_seen"]:
        summary["first_seen"] = created_at
    if summary["last_seen"] is None or created_at > summary["last_seen"]:
        summary["last_seen"] = created_at


def _event_type_from_action(action: ActionLog) -> str:
    return action.action_type


def _target_from_action(action: ActionLog) -> tuple[str | None, str | None]:
    payload = action.payload or {}
    for key in ("card_id", "target_id", "summary_id"):
        if payload.get(key):
            target_type = "card" if key == "card_id" else key.removesuffix("_id")
            return target_type, str(payload[key])
    return None, None


def _json_payload(value: dict | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _event_dt(value: datetime | None, fallback: datetime | None = None) -> datetime | None:
    return value or fallback


def _seconds_since(value: datetime | None, start: datetime | None) -> float:
    if not value or not start:
        return 0.0
    return round(max(0.0, (value - start).total_seconds()), 3)


def _heatmap_weight(event: ResearchEvent) -> float:
    payload = event.payload or {}
    if event.event_type == "ui:click":
        return 1.0
    if event.event_type == "card:detail_open":
        return 1.2
    if event.event_type == "card:visible":
        duration = payload.get("duration_ms")
        ratio = payload.get("ratio")
        duration_weight = min(float(duration) / 9000, 1.5) if isinstance(duration, (int, float)) else 0.8
        ratio_weight = float(ratio) if isinstance(ratio, (int, float)) else 0.7
        return round(max(0.25, duration_weight * ratio_weight), 3)
    if event.event_type == "pointer:sample":
        return 0.35
    return 0.45


def _all_datetimes(
    cards: list[Card],
    reactions: list[Reaction],
    actions: list[ActionLog],
    events: list[ResearchEvent],
) -> list[datetime]:
    values: list[datetime] = []
    values.extend(card.created_at for card in cards if card.created_at)
    values.extend(reaction.created_at for reaction in reactions if reaction.created_at)
    values.extend(action.created_at for action in actions if action.created_at)
    values.extend(_event_dt(event.client_ts, event.created_at) for event in events if _event_dt(event.client_ts, event.created_at))
    return values


def _collect_research_summary(db: Session, wall: Wall) -> dict[str, Any]:
    cards = db.scalars(
        select(Card)
        .where(Card.wall_id == wall.id)
        .options(selectinload(Card.author), selectinload(Card.reactions))
        .order_by(Card.created_at.asc())
    ).all()
    actions = db.scalars(select(ActionLog).where(ActionLog.wall_id == wall.id).order_by(ActionLog.created_at.asc())).all()
    events = db.scalars(select(ResearchEvent).where(ResearchEvent.wall_id == wall.id).order_by(ResearchEvent.created_at.asc())).all()

    user_ids = {card.author_id for card in cards}
    user_ids.update(reaction.user_id for card in cards for reaction in card.reactions)
    user_ids.update(action.user_id for action in actions if action.user_id)
    user_ids.update(event.user_id for event in events if event.user_id)
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    users_by_id = {user.id: user for user in users}

    summaries: dict[str, dict[str, Any]] = {}

    def ensure(user_id: str | None, session_id: str | None = None) -> dict[str, Any]:
        key = _actor_key(user_id, session_id)
        if key not in summaries:
            summaries[key] = _empty_summary(key, users_by_id.get(user_id or ""), session_id)
        if session_id:
            summaries[key]["client_session_ids"].add(session_id)
        return summaries[key]

    for card in cards:
        summary = ensure(card.author_id)
        summary["card_count"] += 1
        summary["event_count"] += 1
        summary["event_counts"]["card:authored"] += 1
        summary["sentiment_counts"][card.sentiment or "unknown"] += 1
        summary["text_lengths"].append(len(card.plain_text or ""))
        _touch(summary, card.created_at)
        _touch(summary, card.updated_at)

        for reaction in card.reactions:
            reaction_summary = ensure(reaction.user_id)
            reaction_summary["reaction_count"] += 1
            reaction_summary["event_count"] += 1
            reaction_summary["event_counts"][f"reaction:{reaction.reaction_type}"] += 1
            _touch(reaction_summary, reaction.created_at)

    for action in actions:
        summary = ensure(action.user_id)
        summary["action_count"] += 1
        summary["event_count"] += 1
        summary["event_counts"][_event_type_from_action(action)] += 1
        _touch(summary, action.created_at)

    for event in events:
        summary = ensure(event.user_id, event.client_session_id)
        summary["research_event_count"] += 1
        summary["event_count"] += 1
        summary["event_counts"][event.event_type] += 1
        _touch(summary, event.created_at)
        _touch(summary, event.client_ts)

    rows = []
    for summary in summaries.values():
        first_seen = summary["first_seen"]
        last_seen = summary["last_seen"]
        active_span_seconds = (last_seen - first_seen).total_seconds() if first_seen and last_seen else 0.0
        text_lengths = summary.pop("text_lengths")
        rows.append(
            {
                **summary,
                "client_session_ids": sorted(summary["client_session_ids"]),
                "event_counts": dict(sorted(summary["event_counts"].items())),
                "sentiment_counts": {
                    key: summary["sentiment_counts"].get(key, 0)
                    for key in ["positive", "neutral", "negative", "unknown"]
                },
                "average_card_text_length": round(sum(text_lengths) / len(text_lengths), 2) if text_lengths else 0.0,
                "first_seen": _iso(first_seen),
                "last_seen": _iso(last_seen),
                "active_span_seconds": round(active_span_seconds, 3),
            }
        )
    rows.sort(key=lambda item: (item["event_count"], item["last_seen"] or ""), reverse=True)
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "wall_id": wall.id,
        "wall_title": wall.title,
        "user_count": len(rows),
        "event_count": sum(row["event_count"] for row in rows),
        "users": rows,
    }


def _dashboard_timeline(
    *,
    cards: list[Card],
    reactions: list[Reaction],
    actions: list[ActionLog],
    events: list[ResearchEvent],
    users_by_id: dict[str, User],
    start: datetime | None,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for card in cards:
        user = users_by_id.get(card.author_id)
        created_at = card.created_at
        timeline.append(
            {
                "id": f"card:{card.id}",
                "source": "card",
                "user_id": card.author_id,
                "user_name": user.nickname if user else "",
                "event_type": "card:authored",
                "target_type": "card",
                "target_id": card.id,
                "x": float(card.x),
                "y": float(card.y),
                "plain_text": card.plain_text,
                "payload": {
                    "sentiment": card.sentiment,
                    "topic_labels": card.topic_labels or [],
                    "reaction_count": sum(reaction_counts(card).values()),
                },
                "created_at": _iso(created_at),
                "offset_seconds": _seconds_since(created_at, start),
            }
        )
    for reaction in reactions:
        user = users_by_id.get(reaction.user_id)
        created_at = reaction.created_at
        timeline.append(
            {
                "id": f"reaction:{reaction.id}",
                "source": "reaction",
                "user_id": reaction.user_id,
                "user_name": user.nickname if user else "",
                "event_type": f"reaction:{reaction.reaction_type}",
                "target_type": "card",
                "target_id": reaction.card_id,
                "x": None,
                "y": None,
                "plain_text": "",
                "payload": {"reaction_type": reaction.reaction_type},
                "created_at": _iso(created_at),
                "offset_seconds": _seconds_since(created_at, start),
            }
        )
    for action in actions:
        user = users_by_id.get(action.user_id or "")
        created_at = action.created_at
        target_type, target_id = _target_from_action(action)
        timeline.append(
            {
                "id": f"action:{action.id}",
                "source": "action_log",
                "user_id": action.user_id,
                "user_name": user.nickname if user else "",
                "event_type": action.action_type,
                "target_type": target_type,
                "target_id": target_id,
                "x": None,
                "y": None,
                "plain_text": "",
                "payload": action.payload or {},
                "created_at": _iso(created_at),
                "offset_seconds": _seconds_since(created_at, start),
            }
        )
    for event in events:
        user = users_by_id.get(event.user_id or "")
        created_at = _event_dt(event.client_ts, event.created_at)
        timeline.append(
            {
                "id": f"research:{event.id}",
                "source": "research_event",
                "user_id": event.user_id,
                "user_name": user.nickname if user else "",
                "event_type": event.event_type,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "x": event.x,
                "y": event.y,
                "plain_text": "",
                "payload": event.payload or {},
                "created_at": _iso(created_at),
                "offset_seconds": _seconds_since(created_at, start),
            }
        )
    return sorted(timeline, key=lambda item: item["created_at"] or "")


def _collect_research_dashboard(db: Session, wall: Wall) -> dict[str, Any]:
    cards = db.scalars(
        select(Card)
        .where(Card.wall_id == wall.id)
        .options(selectinload(Card.author), selectinload(Card.reactions))
        .order_by(Card.created_at.asc())
    ).all()
    card_ids = [card.id for card in cards]
    reactions = db.scalars(select(Reaction).where(Reaction.card_id.in_(card_ids)).order_by(Reaction.created_at.asc())).all() if card_ids else []
    actions = db.scalars(select(ActionLog).where(ActionLog.wall_id == wall.id).order_by(ActionLog.created_at.asc())).all()
    events = db.scalars(select(ResearchEvent).where(ResearchEvent.wall_id == wall.id).order_by(ResearchEvent.created_at.asc())).all()

    user_ids = {card.author_id for card in cards}
    user_ids.update(reaction.user_id for reaction in reactions)
    user_ids.update(action.user_id for action in actions if action.user_id)
    user_ids.update(event.user_id for event in events if event.user_id)
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    users_by_id = {user.id: user for user in users}
    cards_by_id = {card.id: card for card in cards}
    summary = _collect_research_summary(db, wall)
    datetimes = _all_datetimes(cards, reactions, actions, events)
    started_at = min(datetimes) if datetimes else None
    ended_at = max(datetimes) if datetimes else None
    timeline = _dashboard_timeline(cards=cards, reactions=reactions, actions=actions, events=events, users_by_id=users_by_id, start=started_at)
    heatmap_points = []
    for event in events:
        if event.event_type not in {"ui:click", "pointer:sample", "card:visible", "card:detail_open"}:
            continue
        target_card = cards_by_id.get(event.target_id or "")
        x = event.x if event.x is not None else target_card.x if target_card else None
        y = event.y if event.y is not None else target_card.y if target_card else None
        if x is None or y is None:
            continue
        heatmap_points.append(
            {
                "id": event.id,
                "user_id": event.user_id,
                "user_name": users_by_id.get(event.user_id or "").nickname if event.user_id in users_by_id else "",
                "event_type": event.event_type,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "x": float(x),
                "y": float(y),
                "weight": _heatmap_weight(event),
                "created_at": _iso(_event_dt(event.client_ts, event.created_at)),
            }
        )
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "wall": {
            "id": wall.id,
            "title": wall.title,
            "description": wall.description,
            "canvas_width": 1280,
            "canvas_height": wall.canvas_height,
        },
        "metrics": {
            "participants": summary["user_count"],
            "cards": len(cards),
            "reactions": len(reactions),
            "action_events": len(actions),
            "behavior_events": len(events),
            "total_events": len(timeline),
            "started_at": _iso(started_at),
            "ended_at": _iso(ended_at),
            "active_span_seconds": round((ended_at - started_at).total_seconds(), 3) if started_at and ended_at else 0.0,
        },
        "users": summary["users"],
        "cards": [
            {
                "id": card.id,
                "author_id": card.author_id,
                "author_name": card.author.nickname,
                "plain_text": card.plain_text,
                "x": card.x,
                "y": card.y,
                "width": card.width,
                "height": card.height,
                "sentiment": card.sentiment,
                "reaction_count": sum(reaction_counts(card).values()),
                "created_at": _iso(card.created_at),
            }
            for card in cards
        ],
        "heatmap_points": heatmap_points,
        "timeline": timeline,
        "event_rows": list(reversed(timeline[-180:])),
    }


def _timeline_rows(
    wall: Wall,
    users_by_id: dict[str, User],
    cards: list[Card],
    actions: list[ActionLog],
    events: list[ResearchEvent],
    reactions: list[Reaction],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in cards:
        user = users_by_id.get(card.author_id)
        rows.append(
            {
                "source": "card",
                "id": card.id,
                "wall_id": wall.id,
                "user_id": card.author_id,
                "user_name": user.nickname if user else "",
                "email": user.email if user else "",
                "client_session_id": "",
                "event_type": "card:authored_snapshot",
                "target_type": "card",
                "target_id": card.id,
                "plain_text": card.plain_text,
                "x": card.x,
                "y": card.y,
                "payload_json": _json_payload(
                    {
                        "color": card.color,
                        "rotation": card.rotation,
                        "sentiment": card.sentiment,
                        "sentiment_confidence": card.sentiment_confidence,
                        "topic_labels": card.topic_labels or [],
                        "is_deleted": card.is_deleted,
                    }
                ),
                "client_ts": "",
                "created_at": card.created_at.isoformat() if card.created_at else "",
            }
        )
    for reaction in reactions:
        user = users_by_id.get(reaction.user_id)
        rows.append(
            {
                "source": "reaction",
                "id": reaction.id,
                "wall_id": wall.id,
                "user_id": reaction.user_id,
                "user_name": user.nickname if user else "",
                "email": user.email if user else "",
                "client_session_id": "",
                "event_type": f"reaction:{reaction.reaction_type}",
                "target_type": "card",
                "target_id": reaction.card_id,
                "plain_text": "",
                "x": "",
                "y": "",
                "payload_json": _json_payload({"reaction_type": reaction.reaction_type}),
                "client_ts": "",
                "created_at": reaction.created_at.isoformat() if reaction.created_at else "",
            }
        )
    for action in actions:
        user = users_by_id.get(action.user_id or "")
        target_type, target_id = _target_from_action(action)
        rows.append(
            {
                "source": "action_log",
                "id": action.id,
                "wall_id": action.wall_id,
                "user_id": action.user_id or "",
                "user_name": user.nickname if user else "",
                "email": user.email if user else "",
                "client_session_id": "",
                "event_type": action.action_type,
                "target_type": target_type or "",
                "target_id": target_id or "",
                "plain_text": "",
                "x": "",
                "y": "",
                "payload_json": _json_payload(action.payload),
                "client_ts": "",
                "created_at": action.created_at.isoformat() if action.created_at else "",
            }
        )
    for event in events:
        user = users_by_id.get(event.user_id or "")
        rows.append(
            {
                "source": "research_event",
                "id": event.id,
                "wall_id": event.wall_id,
                "user_id": event.user_id or "",
                "user_name": user.nickname if user else "",
                "email": user.email if user else "",
                "client_session_id": event.client_session_id,
                "event_type": event.event_type,
                "target_type": event.target_type or "",
                "target_id": event.target_id or "",
                "plain_text": "",
                "x": event.x if event.x is not None else "",
                "y": event.y if event.y is not None else "",
                "payload_json": _json_payload(
                    {
                        **(event.payload or {}),
                        "viewport_width": event.viewport_width,
                        "viewport_height": event.viewport_height,
                        "canvas_width": event.canvas_width,
                        "canvas_height": event.canvas_height,
                        "client_event_id": event.client_event_id,
                    }
                ),
                "client_ts": event.client_ts.isoformat() if event.client_ts else "",
                "created_at": event.created_at.isoformat() if event.created_at else "",
            }
        )
    return sorted(rows, key=lambda item: item["created_at"] or "")


def _stream_rows(filename: str, rows: list[dict[str, Any]]) -> StreamingResponse:
    output = io.StringIO()
    output.write("\ufeff")
    fieldnames = [
        "source",
        "id",
        "wall_id",
        "user_id",
        "user_name",
        "email",
        "client_session_id",
        "event_type",
        "target_type",
        "target_id",
        "plain_text",
        "x",
        "y",
        "payload_json",
        "client_ts",
        "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/events", response_model=ResearchEventIngestResult)
def ingest_research_events(
    wall_id: str,
    payload: ResearchEventBatch,
    wall_access_token: str | None = Depends(get_wall_access_token),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    _require_wall_for_event(db, wall_id, user, wall_access_token)
    now = _utc_now_naive()
    events = [
        ResearchEvent(
            wall_id=wall_id,
            user_id=user.id if user else None,
            client_session_id=event.client_session_id,
            client_event_id=event.client_event_id,
            event_type=event.event_type,
            target_type=event.target_type,
            target_id=event.target_id,
            x=event.x,
            y=event.y,
            viewport_width=event.viewport_width,
            viewport_height=event.viewport_height,
            canvas_width=event.canvas_width,
            canvas_height=event.canvas_height,
            payload=event.payload,
            client_ts=event.client_ts.replace(tzinfo=None) if event.client_ts else None,
            created_at=now,
        )
        for event in payload.events
    ]
    db.add_all(events)
    db.commit()
    return {"accepted": len(events)}


@router.get("/summary", response_model=ResearchSummary)
def research_summary(
    wall_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    wall = _require_owned_wall(db, wall_id, admin)
    return _collect_research_summary(db, wall)


@router.get("/dashboard", response_model=ResearchDashboard)
def research_dashboard(
    wall_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    wall = _require_owned_wall(db, wall_id, admin)
    return _collect_research_dashboard(db, wall)


@router.get("/export.csv")
def export_research_csv(
    wall_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    wall = _require_owned_wall(db, wall_id, admin)
    cards = db.scalars(select(Card).where(Card.wall_id == wall_id).order_by(Card.created_at.asc())).all()
    card_ids = [card.id for card in cards]
    reactions = db.scalars(select(Reaction).where(Reaction.card_id.in_(card_ids)).order_by(Reaction.created_at.asc())).all() if card_ids else []
    actions = db.scalars(select(ActionLog).where(ActionLog.wall_id == wall_id).order_by(ActionLog.created_at.asc())).all()
    events = db.scalars(select(ResearchEvent).where(ResearchEvent.wall_id == wall_id).order_by(ResearchEvent.created_at.asc())).all()
    user_ids = {card.author_id for card in cards}
    user_ids.update(reaction.user_id for reaction in reactions)
    user_ids.update(action.user_id for action in actions if action.user_id)
    user_ids.update(event.user_id for event in events if event.user_id)
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    users_by_id = {user.id: user for user in users}
    log_action(db, wall_id, admin.id, "wall:export_research_csv", {"row_count": len(cards) + len(reactions) + len(actions) + len(events)})
    db.commit()
    rows = _timeline_rows(wall, users_by_id, cards, actions, events, reactions)
    return _stream_rows(f"{wall.id}-research-timeline.csv", rows)


@router.get("/users/{user_id}/export.csv")
def export_research_user_csv(
    wall_id: str,
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    wall = _require_owned_wall(db, wall_id, admin)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    cards = db.scalars(select(Card).where(Card.wall_id == wall_id, Card.author_id == user_id).order_by(Card.created_at.asc())).all()
    wall_cards = db.scalars(select(Card.id).where(Card.wall_id == wall_id)).all()
    reactions = db.scalars(select(Reaction).where(Reaction.card_id.in_(wall_cards), Reaction.user_id == user_id).order_by(Reaction.created_at.asc())).all() if wall_cards else []
    actions = db.scalars(select(ActionLog).where(ActionLog.wall_id == wall_id, ActionLog.user_id == user_id).order_by(ActionLog.created_at.asc())).all()
    events = db.scalars(select(ResearchEvent).where(ResearchEvent.wall_id == wall_id, ResearchEvent.user_id == user_id).order_by(ResearchEvent.created_at.asc())).all()
    users_by_id = {user.id: user}
    log_action(
        db,
        wall_id,
        admin.id,
        "wall:export_research_user_csv",
        {"user_id": user_id, "row_count": len(cards) + len(reactions) + len(actions) + len(events)},
    )
    db.commit()
    rows = _timeline_rows(wall, users_by_id, cards, actions, events, reactions)
    return _stream_rows(f"{wall.id}-{user.id}-research.csv", rows)
