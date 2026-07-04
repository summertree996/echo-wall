from collections import Counter

from app.models import Card, Wall


def iso(value) -> str:
    return value.isoformat() if value else ""


def reaction_counts(card: Card) -> dict[str, int]:
    counts = Counter(normalize_reaction_type(reaction.reaction_type) for reaction in card.reactions)
    return {key: counts.get(key, 0) for key in ["like", "dislike", "question"]}


def normalize_reaction_type(reaction_type: str) -> str:
    if reaction_type == "idea":
        return "like"
    if reaction_type == "fire":
        return "dislike"
    return reaction_type


def card_to_public(card: Card, current_user_id: str | None = None) -> dict:
    own_reactions = {
        normalize_reaction_type(reaction.reaction_type)
        for reaction in card.reactions
        if current_user_id and reaction.user_id == current_user_id
    }
    return {
        "id": card.id,
        "wall_id": card.wall_id,
        "author_id": card.author_id,
        "author_name": card.author.nickname,
        "content_json": card.content_json,
        "plain_text": card.plain_text,
        "x": card.x,
        "y": card.y,
        "width": card.width,
        "height": card.height,
        "color": card.color,
        "rotation": float(card.rotation),
        "z_index": card.z_index,
        "sentiment": card.sentiment,
        "sentiment_confidence": card.sentiment_confidence,
        "topic_labels": card.topic_labels or [],
        "reaction_counts": reaction_counts(card),
        "own_reactions": [reaction_type for reaction_type in ["like", "dislike", "question"] if reaction_type in own_reactions],
        "is_deleted": card.is_deleted,
        "created_at": iso(card.created_at),
        "updated_at": iso(card.updated_at),
    }


def wall_to_public(wall: Wall, card_count: int = 0) -> dict:
    return {
        "id": wall.id,
        "title": wall.title,
        "description": wall.description,
        "access_mode": wall.access_mode,
        "has_password": bool(wall.password_hash),
        "canvas_height": wall.canvas_height,
        "is_anonymous": wall.is_anonymous,
        "is_archived": wall.is_archived,
        "is_locked": wall.is_locked,
        "spotlight_card_id": wall.spotlight_card_id,
        "ai_enabled": wall.ai_enabled,
        "ai_model": wall.ai_model,
        "ai_thinking_enabled": wall.ai_thinking_enabled,
        "ai_reasoning_effort": wall.ai_reasoning_effort,
        "owner_id": wall.owner_id,
        "created_at": iso(wall.created_at),
        "updated_at": iso(wall.updated_at),
        "card_count": card_count,
    }
