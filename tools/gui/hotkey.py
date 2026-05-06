from __future__ import annotations

from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


class HotkeyTool(BaseTool):
    spec = ToolSpec(
        name="gui.hotkey",
        description="Press a key combination.",
        input_schema={
            "type": "object",
            "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
            "required": ["keys"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "pyautogui")
            keys = params["keys"]
            if not isinstance(keys, list) or not keys:
                raise ValueError("keys must be a non-empty list")
            str_keys = [str(k) for k in keys]
            if len(str_keys) == 1:
                provider.press(str_keys[0])
                return ToolResult(success=True, data={"keys": str_keys}, evidence=["press:" + str_keys[0]])
            provider.hotkey(*str_keys)
            return ToolResult(success=True, data={"keys": str_keys}, evidence=["hotkey:" + "+".join(str_keys)])
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
