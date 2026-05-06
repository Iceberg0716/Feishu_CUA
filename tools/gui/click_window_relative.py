from __future__ import annotations

from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


class ClickWindowRelativeTool(BaseTool):
    spec = ToolSpec(
        name="gui.click_window_relative",
        description="Focus a window by title keywords and click at a relative position inside its rect.",
        input_schema={
            "type": "object",
            "properties": {
                "title_keywords": {"type": "array", "items": {"type": "string"}},
                "x_ratio": {"type": "number"},
                "y_ratio": {"type": "number"},
                "clicks": {"type": "integer"},
                "interval": {"type": "number"},
                "button": {"type": "string"},
            },
            "required": ["title_keywords", "x_ratio", "y_ratio"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            win_provider = get_provider(context, "pywinauto")
            mouse_provider = get_provider(context, "pyautogui")

            keywords = params["title_keywords"]
            if not isinstance(keywords, list) or not keywords:
                raise ValueError("title_keywords must be a non-empty list")

            x_ratio = _clamp01(float(params["x_ratio"]))
            y_ratio = _clamp01(float(params["y_ratio"]))
            clicks = int(params.get("clicks", 1))
            interval = float(params.get("interval", 0.0))
            button = str(params.get("button", "left"))

            out = win_provider.focus_window_and_get_rect([str(k) for k in keywords])
            rect = out.get("rect") if isinstance(out, dict) else None
            if not isinstance(rect, dict):
                raise ValueError("window rect missing")

            left = int(rect.get("left", 0))
            top = int(rect.get("top", 0))
            right = int(rect.get("right", 0))
            bottom = int(rect.get("bottom", 0))
            w = max(1, right - left)
            h = max(1, bottom - top)
            x = left + int(w * x_ratio)
            y = top + int(h * y_ratio)

            mouse_provider.click(x, y, clicks=clicks, interval=interval, button=button)
            title = str(out.get("title") or "")
            ev = [f"focused_window:{title}" if title else "focused_window", f"click_window_relative:{x_ratio:.2f},{y_ratio:.2f}->{x},{y}"]
            return ToolResult(success=True, data={"title": title, "x": x, "y": y, "x_ratio": x_ratio, "y_ratio": y_ratio}, evidence=ev)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = ["ClickWindowRelativeTool"]

