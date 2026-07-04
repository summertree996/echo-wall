from collections import Counter
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.deepseek import deepseek_client
from app.api.deps import require_admin
from app.db import get_db
from app.models import AiSummaryCache, Card, User, Wall
from app.schemas.ai import AiConnectionTestPublic, AiConnectionTestRequest
from app.schemas.summary import WallSummaryDiffPublic, WallSummaryHistoryItem, WallSummaryPublic
from app.services.action_log import log_action
from app.services.serializers import reaction_counts


router = APIRouter(prefix="/walls/{wall_id}/ai", tags=["ai"])
_SUMMARY_LOCKS: dict[str, asyncio.Lock] = {}
_SUMMARY_LOCKS_GUARD = asyncio.Lock()


async def _summary_lock_for(wall_id: str) -> asyncio.Lock:
    async with _SUMMARY_LOCKS_GUARD:
        lock = _SUMMARY_LOCKS.get(wall_id)
        if lock is None:
            lock = asyncio.Lock()
            _SUMMARY_LOCKS[wall_id] = lock
        return lock


def _evidence(card: Card) -> dict[str, Any]:
    return {
        "id": card.id,
        "text": card.plain_text[:260],
        "sentiment": card.sentiment,
        "reaction_count": sum(reaction_counts(card).values()),
    }


def _attach_evidence(items: list[dict[str, Any]], by_id: dict[str, Card]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in items[:4]:
        ids = item.get("evidence_card_ids") if isinstance(item.get("evidence_card_ids"), list) else []
        evidence = [_evidence(by_id[card_id]) for card_id in ids[:3] if card_id in by_id]
        output.append(
            {
                "title": str(item.get("title") or "观察")[:40],
                "summary": str(item.get("summary") or "")[:240],
                "severity": str(item.get("severity") or "medium")[:16],
                "evidence": evidence,
            }
        )
    return output


def _summary_cache_key(wall: Wall, cards: list[Card]) -> str:
    source = {
        "wall_id": wall.id,
        "model": wall.ai_model,
        "thinking": wall.ai_thinking_enabled,
        "reasoning_effort": wall.ai_reasoning_effort,
        "cards": [
            {
                "id": card.id,
                "updated_at": card.updated_at.isoformat() if card.updated_at else "",
                "sentiment": card.sentiment,
                "topics": card.topic_labels or [],
                "reactions": sum(reaction_counts(card).values()),
                "deleted": card.is_deleted,
            }
            for card in cards
        ],
    }
    raw = json.dumps(source, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require_owned_wall(db: Session, wall_id: str, admin: User) -> Wall:
    wall = db.get(Wall, wall_id)
    if not wall or wall.is_archived or wall.owner_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wall not found")
    return wall


def _cache_to_summary_public(cached: AiSummaryCache, *, cached_result: bool = True) -> dict:
    payload = dict(cached.payload or {})
    payload.update(
        {
            "summary_id": cached.id,
            "generated_at": cached.generated_at,
            "model": cached.model,
            "thinking_enabled": cached.thinking_enabled,
            "reasoning_effort": cached.reasoning_effort,
            "cached": cached_result,
            "cache_key": cached.cache_key,
            "card_count": cached.card_count,
        }
    )
    return payload


def _latest_summary_cache(db: Session, wall_id: str) -> AiSummaryCache | None:
    return db.scalar(
        select(AiSummaryCache)
        .where(AiSummaryCache.wall_id == wall_id)
        .order_by(AiSummaryCache.generated_at.desc())
    )


def _payload_titles(payload: dict[str, Any], key: str) -> set[str]:
    items = payload.get(key) if isinstance(payload.get(key), list) else []
    return {str(item.get("title")).strip() for item in items if isinstance(item, dict) and str(item.get("title") or "").strip()}


def _representative_ids(payload: dict[str, Any]) -> set[str]:
    items = payload.get("representative_cards") if isinstance(payload.get("representative_cards"), list) else []
    return {str(item.get("id")).strip() for item in items if isinstance(item, dict) and str(item.get("id") or "").strip()}


def _sentiment_counts(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("sentiment_counts") if isinstance(payload.get("sentiment_counts"), dict) else {}
    return {key: int(raw.get(key) or 0) for key in ["positive", "neutral", "negative", "unknown"]}


def _summary_diff(current: AiSummaryCache, previous: AiSummaryCache) -> dict:
    current_payload = current.payload or {}
    previous_payload = previous.payload or {}
    current_sentiment = _sentiment_counts(current_payload)
    previous_sentiment = _sentiment_counts(previous_payload)
    key_points_current = _payload_titles(current_payload, "key_points")
    key_points_previous = _payload_titles(previous_payload, "key_points")
    risks_current = _payload_titles(current_payload, "risks")
    risks_previous = _payload_titles(previous_payload, "risks")
    representative_current = _representative_ids(current_payload)
    representative_previous = _representative_ids(previous_payload)
    return {
        "summary_id": current.id,
        "against_id": previous.id,
        "generated_at": current.generated_at,
        "against_generated_at": previous.generated_at,
        "card_count_delta": current.card_count - previous.card_count,
        "sentiment_delta": {key: current_sentiment[key] - previous_sentiment[key] for key in current_sentiment},
        "key_points_added": sorted(key_points_current - key_points_previous),
        "key_points_removed": sorted(key_points_previous - key_points_current),
        "risks_added": sorted(risks_current - risks_previous),
        "risks_removed": sorted(risks_previous - risks_current),
        "representative_cards_added": sorted(representative_current - representative_previous),
        "representative_cards_removed": sorted(representative_previous - representative_current),
        "overview_changed": str(current_payload.get("overview") or "") != str(previous_payload.get("overview") or ""),
    }


@router.post("/test", response_model=AiConnectionTestPublic)
async def test_ai_connection(
    wall_id: str,
    payload: AiConnectionTestRequest | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    wall = _require_owned_wall(db, wall_id, admin)
    if not deepseek_client.configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DeepSeek API key is not configured")

    selected_model = payload.ai_model if payload and payload.ai_model is not None else wall.ai_model
    selected_thinking = payload.ai_thinking_enabled if payload and payload.ai_thinking_enabled is not None else wall.ai_thinking_enabled
    selected_effort = payload.ai_reasoning_effort if payload and payload.ai_reasoning_effort is not None else wall.ai_reasoning_effort
    started = perf_counter()
    try:
        result = await deepseek_client.test_connection(
            model=selected_model,
            thinking=selected_thinking,
            reasoning_effort=selected_effort,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="DeepSeek connection test failed") from exc
    if not result:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DeepSeek connection test returned no JSON")

    latency_ms = max(0, round((perf_counter() - started) * 1000))
    response = {
        "status": "ok" if result.get("ok") else "unexpected",
        "model": deepseek_client.normalize_model(selected_model),
        "thinking_enabled": selected_thinking,
        "reasoning_effort": deepseek_client.normalize_reasoning_effort(selected_effort),
        "latency_ms": latency_ms,
        "message": str(result.get("message") or "DeepSeek 连接正常")[:120],
    }
    log_action(db, wall_id, admin.id, "ai:test", {"model": response["model"], "latency_ms": latency_ms})
    db.commit()
    return response


@router.post("/summary", response_model=WallSummaryPublic)
async def summarize_wall(
    wall_id: str,
    refresh: bool = Query(default=False),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    wall = _require_owned_wall(db, wall_id, admin)
    if not wall.ai_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI analysis is disabled for this wall")

    cards = db.scalars(
        select(Card)
        .where(Card.wall_id == wall_id, Card.is_deleted == False)  # noqa: E712
        .options(selectinload(Card.reactions), selectinload(Card.author))
        .order_by(Card.created_at.asc())
    ).all()
    by_id = {card.id: card for card in cards}
    sentiment_counts = Counter(card.sentiment or "unknown" for card in cards)
    cache_key = _summary_cache_key(wall, cards)
    if not refresh:
        cached = db.scalar(
            select(AiSummaryCache)
            .where(AiSummaryCache.wall_id == wall_id, AiSummaryCache.cache_key == cache_key)
            .order_by(AiSummaryCache.generated_at.desc())
        )
        if cached:
            return _cache_to_summary_public(cached, cached_result=True)

    summary_lock = await _summary_lock_for(wall_id)
    if summary_lock.locked():
        latest = _latest_summary_cache(db, wall_id)
        if latest:
            return _cache_to_summary_public(latest, cached_result=True)

    async with summary_lock:
        if not refresh:
            cached = db.scalar(
                select(AiSummaryCache)
                .where(AiSummaryCache.wall_id == wall_id, AiSummaryCache.cache_key == cache_key)
                .order_by(AiSummaryCache.generated_at.desc())
            )
            if cached:
                return _cache_to_summary_public(cached, cached_result=True)

        card_payload = [
            {
                "id": card.id,
                "text": card.plain_text,
                "sentiment": card.sentiment,
                "topics": card.topic_labels or [],
                "reactions": sum(reaction_counts(card).values()),
            }
            for card in cards
        ]
        try:
            ai_result = await deepseek_client.summarize_wall(
                wall.title,
                card_payload,
                model=wall.ai_model,
                thinking=wall.ai_thinking_enabled,
                reasoning_effort=wall.ai_reasoning_effort,
            )
        except Exception as exc:
            latest = _latest_summary_cache(db, wall_id)
            if latest:
                return _cache_to_summary_public(latest, cached_result=True)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI summary failed") from exc
        if not ai_result:
            latest = _latest_summary_cache(db, wall_id)
            if latest:
                return _cache_to_summary_public(latest, cached_result=True)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI summary unavailable")

        key_points = _attach_evidence(ai_result.get("key_points") if isinstance(ai_result.get("key_points"), list) else [], by_id)
        risks = _attach_evidence(ai_result.get("risks") if isinstance(ai_result.get("risks"), list) else [], by_id)
        representative_ids = ai_result.get("representative_card_ids") if isinstance(ai_result.get("representative_card_ids"), list) else []
        representative_cards = [_evidence(by_id[card_id]) for card_id in representative_ids[:5] if card_id in by_id]
        if not representative_cards:
            representative_cards = [_evidence(card) for card in sorted(cards, key=lambda item: sum(reaction_counts(item).values()), reverse=True)[:3]]

        generated_at = datetime.now(timezone.utc)
        response = {
            "summary_id": None,
            "generated_at": generated_at,
            "model": wall.ai_model,
            "thinking_enabled": wall.ai_thinking_enabled,
            "reasoning_effort": wall.ai_reasoning_effort,
            "cached": False,
            "cache_key": cache_key,
            "card_count": len(cards),
            "overview": str(ai_result.get("overview") or "")[:360],
            "sentiment_counts": {
                "positive": sentiment_counts.get("positive", 0),
                "neutral": sentiment_counts.get("neutral", 0),
                "negative": sentiment_counts.get("negative", 0),
                "unknown": sentiment_counts.get("unknown", 0),
            },
            "key_points": [{key: value for key, value in item.items() if key != "severity"} for item in key_points],
            "risks": risks,
            "representative_cards": representative_cards,
        }
        cache = AiSummaryCache(
            wall_id=wall_id,
            cache_key=cache_key,
            model=wall.ai_model,
            thinking_enabled=wall.ai_thinking_enabled,
            reasoning_effort=wall.ai_reasoning_effort,
            card_count=len(cards),
            payload={key: value for key, value in response.items() if key not in {"summary_id", "generated_at", "cached", "cache_key", "card_count"}},
            generated_by_id=admin.id,
            generated_at=generated_at,
        )
        db.add(cache)
        db.flush()
        response["summary_id"] = cache.id
        log_action(db, wall_id, admin.id, "ai:summary", {"card_count": len(cards), "model": wall.ai_model, "refresh": refresh})
        db.commit()

        return response


@router.get("/summary/history", response_model=list[WallSummaryHistoryItem])
def list_summary_history(
    wall_id: str,
    limit: int = Query(default=8, ge=1, le=30),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    _require_owned_wall(db, wall_id, admin)
    rows = db.scalars(
        select(AiSummaryCache)
        .where(AiSummaryCache.wall_id == wall_id)
        .order_by(AiSummaryCache.generated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": item.id,
            "generated_at": item.generated_at,
            "model": item.model,
            "thinking_enabled": item.thinking_enabled,
            "reasoning_effort": item.reasoning_effort,
            "card_count": item.card_count,
            "cache_key": item.cache_key,
            "overview": str((item.payload or {}).get("overview") or "")[:140],
        }
        for item in rows
    ]


@router.get("/summary/history/{summary_id}", response_model=WallSummaryPublic)
def get_summary_history_item(
    wall_id: str,
    summary_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    _require_owned_wall(db, wall_id, admin)
    cached = db.scalar(select(AiSummaryCache).where(AiSummaryCache.wall_id == wall_id, AiSummaryCache.id == summary_id))
    if not cached:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    return _cache_to_summary_public(cached, cached_result=True)


@router.get("/summary/history/{summary_id}/diff", response_model=WallSummaryDiffPublic)
def diff_summary_history_item(
    wall_id: str,
    summary_id: str,
    against_id: str | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    _require_owned_wall(db, wall_id, admin)
    current = db.scalar(select(AiSummaryCache).where(AiSummaryCache.wall_id == wall_id, AiSummaryCache.id == summary_id))
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    if against_id:
        previous = db.scalar(select(AiSummaryCache).where(AiSummaryCache.wall_id == wall_id, AiSummaryCache.id == against_id))
    else:
        previous = db.scalar(
            select(AiSummaryCache)
            .where(AiSummaryCache.wall_id == wall_id, AiSummaryCache.generated_at < current.generated_at)
            .order_by(AiSummaryCache.generated_at.desc())
        )
    if not previous:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Previous summary not found")
    return _summary_diff(current, previous)
