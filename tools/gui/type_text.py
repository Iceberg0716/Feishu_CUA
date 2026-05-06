from __future__ import annotations

from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


class TypeTextTool(BaseTool):
    spec = ToolSpec(
        name="gui.type_text",
        description="Type text into the active input.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}, "interval": {"type": "number"}, "replace": {"type": "boolean"}},
            "required": ["text"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "pyautogui")
            text = str(params["text"])
            interval = float(params.get("interval", 0.0))
            replace = bool(params.get("replace", False))
            provider.type_text(text, interval=interval, replace=replace)
            ev = [f"type_text:{len(text)}"]
            if replace:
                ev.append("type_replace:true")
            return ToolResult(success=True, data={"typed": len(text), "replace": replace}, evidence=ev)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
