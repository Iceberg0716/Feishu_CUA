from __future__ import annotations

from typing import Any

from runtime.context import RunContext
from tools.schema import ToolResult


def tool_call(context: RunContext, name: str, params: dict[str, Any]) -> ToolResult:
    tool = context.tool_registry.get(name)
    return tool.execute(params, context)


def config_get(context: RunContext, path: str, default: Any = None) -> Any:
    cfg = context.metadata.get("config")
    if not isinstance(cfg, dict):
        return default
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

