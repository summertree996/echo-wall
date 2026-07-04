import json
from typing import Any


MAX_CARD_TEXT_LENGTH = 150
MAX_CARD_CONTENT_BYTES = 10_000
MAX_CONTENT_DEPTH = 24

ALLOWED_NODE_TYPES = {
    "doc",
    "paragraph",
    "text",
    "bulletList",
    "orderedList",
    "listItem",
    "hardBreak",
}
ALLOWED_MARK_TYPES = {"bold", "italic", "strike", "underline"}


class ContentValidationError(ValueError):
    pass


def extract_text_from_content_json(content_json: dict[str, Any]) -> str:
    text_parts: list[str] = []

    def walk_node(node: Any, depth: int = 0) -> None:
        if depth > MAX_CONTENT_DEPTH:
            raise ContentValidationError("Content is too deeply nested")
        if not isinstance(node, dict):
            raise ContentValidationError("Content nodes must be objects")

        node_type = node.get("type")
        if not isinstance(node_type, str) or node_type not in ALLOWED_NODE_TYPES:
            raise ContentValidationError("Unsupported rich text node")

        marks = node.get("marks", [])
        if marks:
            if not isinstance(marks, list):
                raise ContentValidationError("Rich text marks must be a list")
            for mark in marks:
                if not isinstance(mark, dict) or mark.get("type") not in ALLOWED_MARK_TYPES:
                    raise ContentValidationError("Unsupported rich text mark")

        if node_type == "text":
            text = node.get("text")
            if not isinstance(text, str):
                raise ContentValidationError("Text node is missing text")
            text_parts.append(text)
            return

        if node_type == "hardBreak":
            text_parts.append("\n")

        content = node.get("content", [])
        if content:
            if not isinstance(content, list):
                raise ContentValidationError("Rich text content must be a list")
            for child in content:
                walk_node(child, depth + 1)

    walk_node(content_json)
    return "".join(text_parts)


def validate_card_content(content_json: dict[str, Any], plain_text: str | None = None) -> str:
    try:
        raw = json.dumps(content_json, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ContentValidationError("Content JSON is not serializable") from exc
    if len(raw.encode("utf-8")) > MAX_CARD_CONTENT_BYTES:
        raise ContentValidationError("Content JSON is too large")

    extracted_text = extract_text_from_content_json(content_json).strip()
    if not extracted_text:
        raise ContentValidationError("Card text cannot be empty")
    if len(extracted_text) > MAX_CARD_TEXT_LENGTH:
        raise ContentValidationError(f"Card text cannot exceed {MAX_CARD_TEXT_LENGTH} characters")
    if plain_text is not None and len(plain_text.strip()) > MAX_CARD_TEXT_LENGTH:
        raise ContentValidationError(f"Card text cannot exceed {MAX_CARD_TEXT_LENGTH} characters")
    return extracted_text
