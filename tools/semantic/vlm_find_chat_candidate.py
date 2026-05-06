from __future__ import annotations

from pathlib import Path

from runtime.context import RunContext
from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec


def _resolve_path(raw: str, context: RunContext) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (Path(context.artifacts_dir) / p).resolve()


class VlmFindChatCandidateTool(BaseTool):
    spec = ToolSpec(
        name="vlm.find_chat_candidate",
        description="Use VLM to find the most likely Feishu chat candidate bbox/click point on Ctrl+K search results page.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "chat_name": {"type": "string"},
                "search_box_max_y": {"type": "integer"},
                "timeout_seconds": {"type": "integer"},
            },
            "required": ["path", "chat_name"],
        },
        output_schema={"type": "object"},
        timeout=90,
        retryable=True,
        side_effect=False,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "vlm")
            path = _resolve_path(str(params["path"]), context)
            chat_name = str(params["chat_name"])
            search_box_max_y = params.get("search_box_max_y")
            sb_y: int | None
            if search_box_max_y is None:
                sb_y = None
            else:
                sb_y = int(search_box_max_y)
            timeout_seconds = int(params.get("timeout_seconds", 30))
            out = provider.find_chat_candidate(path, chat_name=chat_name, search_box_max_y=sb_y, timeout_seconds=timeout_seconds)
            evidence = [str(path)] + list(out.get("evidence") or [])
            return ToolResult(
                success=bool(out.get("success")),
                data={"bbox": out.get("bbox"), "click_point": out.get("click_point"), "reason": out.get("reason"), "chat_name": chat_name},
                evidence=evidence,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = ["VlmFindChatCandidateTool"]

