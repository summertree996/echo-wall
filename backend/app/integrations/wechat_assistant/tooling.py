from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm import Session


ToolHandler = Callable[[dict[str, Any], Session], Any]


@dataclass
class ToolRunContext:
    source_user_id: str | None
    source_type: str
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: ToolHandler


_LOCAL = threading.local()
_TOOLS: dict[str, ToolSpec] = {}


def set_tool_context(ctx: ToolRunContext | None) -> None:
    if ctx is None:
        if hasattr(_LOCAL, "ctx"):
            delattr(_LOCAL, "ctx")
        return
    _LOCAL.ctx = ctx


def current_tool_context() -> ToolRunContext | None:
    return getattr(_LOCAL, "ctx", None)


def register_tool(spec: ToolSpec) -> ToolSpec:
    if not spec.name.startswith(("list_", "get_", "search_", "resolve_", "prepare_", "summarize_", "classify_")):
        raise ValueError(f"tool name not allowed: {spec.name}")
    _TOOLS[spec.name] = spec
    return spec


def tool(*, name: str, description: str, parameters_schema: dict[str, Any]) -> Callable[[ToolHandler], ToolHandler]:
    def _wrap(fn: ToolHandler) -> ToolHandler:
        register_tool(ToolSpec(name=name, description=description, parameters_schema=parameters_schema, handler=fn))
        return fn

    return _wrap


def get_tools(names: list[str] | None = None) -> list[ToolSpec]:
    if names is None:
        return list(_TOOLS.values())
    return [_TOOLS[name] for name in names if name in _TOOLS]


def clear_tools_for_tests() -> None:
    _TOOLS.clear()
