from __future__ import annotations

from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


class ScrollTool(BaseTool):
    spec = ToolSpec(
        name="gui.scroll",
        description="Scroll mouse wheel by clicks (optionally move cursor first).",
        input_schema={
            "type": "object",
            "properties": {"clicks": {"type": "integer"}, "x": {"type": "integer"}, "y": {"type": "integer"}},
            "required": ["clicks"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "pyautogui")
            clicks = int(params["clicks"])
            x = params.get("x")
            y = params.get("y")
            x_i = int(x) if x is not None else None
            y_i = int(y) if y is not None else None
            provider.scroll(clicks, x=x_i, y=y_i)
            ev = [f"scroll:{clicks}"]
            if x_i is not None and y_i is not None:
                ev.append(f"scroll_at:{x_i},{y_i}")
            return ToolResult(success=True, data={"clicks": clicks, "x": x_i, "y": y_i}, evidence=ev)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
