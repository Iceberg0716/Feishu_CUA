from __future__ import annotations

import time

from tools.base import BaseTool
from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


class WaitTool(BaseTool):
    spec = ToolSpec(
        name="gui.wait",
        description="Wait fixed seconds.",
        input_schema={
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"],
        },
        output_schema={"type": "object"},
        timeout=60,
        retryable=True,
        side_effect=False,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            seconds = float(params["seconds"])
            if seconds < 0:
                raise ValueError("seconds must be >= 0")
            time.sleep(seconds)
            return ToolResult(success=True, data={"seconds": seconds}, evidence=[f"wait_seconds:{seconds}"])
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

