from __future__ import annotations

from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


class FocusWindowTool(BaseTool):
    spec = ToolSpec(
        name="gui.focus_window",
        description="Focus Feishu/Lark window by title keywords.",
        input_schema={
            "type": "object",
            "properties": {"title_keywords": {"type": "array", "items": {"type": "string"}}},
            "required": ["title_keywords"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "pywinauto")
            keywords = params["title_keywords"]
            if not isinstance(keywords, list) or not keywords:
                raise ValueError("title_keywords must be a non-empty list")
            title = provider.focus_window([str(k) for k in keywords])
            return ToolResult(success=True, data={"title": title}, evidence=[f"focused_window:{title}"])
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

