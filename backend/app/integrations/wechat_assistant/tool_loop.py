from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings

from .tooling import ToolRunContext, ToolSpec, set_tool_context


@dataclass
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    status: str
    elapsed_ms: int
    result_preview: str = ""
    error_message: str | None = None


@dataclass
class ToolLoopResult:
    final_text: str
    status: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    error_message: str | None = None
    raw_usage: dict[str, Any] | None = None


def _truncate(value: str, limit: int = 600_000) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}\n...[truncated {len(value) - limit} chars]"


def _strip_json_code_fence(value: str) -> str:
    text = value.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _load_json_fragment(value: str) -> Any:
    text = _strip_json_code_fence(value)
    candidates = [text]
    starts = sorted(pos for pos in (text.find("{"), text.find("[")) if pos >= 0)
    candidates.extend(text[pos:] for pos in starts)
    decoder = json.JSONDecoder()
    last_error: Exception | None = None
    for candidate in dict.fromkeys(candidates):
        try:
            return json.loads(candidate)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        try:
            parsed, _ = decoder.raw_decode(candidate)
            return parsed
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise ValueError("invalid_json_arguments") from last_error


def _parse_tool_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        parsed: Any = value
    elif isinstance(value, str):
        current = value
        parsed = None
        for _ in range(3):
            parsed = _load_json_fragment(current)
            if isinstance(parsed, str):
                current = parsed
                continue
            break
    else:
        try:
            parsed = dict(value or {})
        except Exception:  # noqa: BLE001
            parsed = {}
    if not isinstance(parsed, dict):
        return {}
    for wrapper_key in ("arguments", "args", "parameters", "input"):
        wrapped = parsed.get(wrapper_key)
        if wrapped is None:
            continue
        if len(parsed) == 1 or wrapper_key == "arguments":
            return _parse_tool_arguments(wrapped)
    return dict(parsed)


def _tool_schema(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters_schema,
        },
    }


class DeepSeekToolLoop:
    def __init__(
        self,
        *,
        model: str,
        thinking: bool,
        reasoning_effort: str,
        max_turns: int = 6,
        max_output_tokens: int = 5000,
        temperature: float = 0.2,
    ) -> None:
        self.settings = get_settings()
        self.model = model
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort
        self.max_turns = max(1, max_turns)
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        api_key = self.settings.resolved_deepseek_key()
        if not api_key:
            raise RuntimeError("deepseek_key_missing")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "thinking": {"type": "enabled" if self.thinking else "disabled"},
        }
        if self.thinking:
            payload["reasoning_effort"] = self.reasoning_effort
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        with httpx.Client(timeout=self.settings.deepseek_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.deepseek_api_base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def run(
        self,
        *,
        user_text: str,
        instructions: str,
        tools: list[ToolSpec],
        context: ToolRunContext,
        db: Session,
    ) -> ToolLoopResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_text},
        ]
        schema = [_tool_schema(spec) for spec in tools]
        spec_by_name = {spec.name: spec for spec in tools}
        records: list[ToolCallRecord] = []
        raw_usage: dict[str, Any] = {"turns": []}
        set_tool_context(context)
        try:
            for turn in range(self.max_turns):
                response = self._chat(messages, schema)
                choice = response["choices"][0]
                message = choice["message"]
                raw_usage["turns"].append({"turn": turn, "usage": response.get("usage")})
                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": message.get("content") or "",
                }
                if message.get("reasoning_content"):
                    assistant_message["reasoning_content"] = message.get("reasoning_content")
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls
                messages.append(assistant_message)
                if not tool_calls:
                    return ToolLoopResult(
                        final_text=message.get("content") or "",
                        status="succeeded",
                        tool_calls=records,
                        raw_usage=raw_usage,
                    )
                for item in tool_calls:
                    fn = item.get("function") or {}
                    name = str(fn.get("name") or "")
                    args_raw = fn.get("arguments") or "{}"
                    try:
                        args = _parse_tool_arguments(args_raw)
                        parse_error = None
                    except Exception as exc:  # noqa: BLE001
                        args = {}
                        parse_error = f"invalid_tool_arguments: {exc}"
                    started = time.perf_counter()
                    spec = spec_by_name.get(name)
                    if parse_error:
                        result = {
                            "ok": False,
                            "error": "invalid_tool_arguments",
                            "message": "工具参数 JSON 解析失败，请使用合法 JSON 对象重新调用该工具。",
                        }
                        status = "error"
                        error = parse_error
                    elif not spec:
                        result: Any = {"ok": False, "error": "tool_not_allowed"}
                        status = "error"
                        error = "tool_not_allowed"
                    else:
                        try:
                            result = spec.handler(args, db)
                            status = "ok"
                            error = None
                        except Exception as exc:  # noqa: BLE001
                            result = {"ok": False, "error": type(exc).__name__, "message": str(exc)}
                            status = "error"
                            error = f"{type(exc).__name__}: {exc}"
                    content = _truncate(json.dumps(result, ensure_ascii=False, default=str))
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    records.append(
                        ToolCallRecord(
                            name=name,
                            args=args,
                            status=status,
                            elapsed_ms=elapsed_ms,
                            result_preview=_truncate(content, 800),
                            error_message=error,
                        )
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": item.get("id") or f"call_{turn}_{len(records)}",
                            "name": name,
                            "content": content,
                        }
                    )
            return ToolLoopResult(
                final_text="这次需要查询的内容比较多，我先停在这里。你可以指定一面墙或一个更具体的问题继续问。",
                status="max_turns",
                tool_calls=records,
                error_message="max_turns_exceeded",
                raw_usage=raw_usage,
            )
        finally:
            set_tool_context(None)
