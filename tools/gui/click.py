from __future__ import annotations

from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


class ClickTool(BaseTool):
    spec = ToolSpec(
        name="gui.click",
        description="Click at screen coordinates.",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "clicks": {"type": "integer"},
                "interval": {"type": "number"},
                "button": {"type": "string"},
            },
            "required": ["x", "y"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "pyautogui")
            x = int(params["x"])
            y = int(params["y"])
            clicks = int(params.get("clicks", 1))
            interval = float(params.get("interval", 0.0))
            button = str(params.get("button", "left"))
            provider.click(x, y, clicks=clicks, interval=interval, button=button)
            return ToolResult(success=True, data={"x": x, "y": y}, evidence=[f"click:{x},{y}"])
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

