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


class ClickCroppedScreenshotPointTool(BaseTool):
    spec = ToolSpec(
        name="gui.click_cropped_screenshot_point",
        description=(
            "Click a point that is defined in screenshot coordinates for a screenshot that was cropped to the target window. "
            "This tool converts (x,y) from the cropped screenshot coordinate space into absolute screen coordinates by "
            "re-focusing the window and using its rect."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title_keywords": {"type": "array", "items": {"type": "string"}},
                "path": {"type": "string", "description": "Screenshot path that was cropped to the window."},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["title_keywords", "path", "x", "y"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            keywords = params.get("title_keywords")
            if not isinstance(keywords, list) or not keywords:
                raise ValueError("title_keywords must be a non-empty list")
            x = int(params["x"])
            y = int(params["y"])
            path = _resolve_path(str(params["path"]), context)

            # Re-focus and get current window rect in the same coordinate system that click uses.
            win = get_provider(context, "pywinauto")
            out = win.focus_window_and_get_rect([str(k) for k in keywords])
            rect = out.get("rect") if isinstance(out, dict) else None
            if not isinstance(rect, dict):
                raise ValueError("window rect missing")
            left = int(rect.get("left", 0))
            top = int(rect.get("top", 0))

            # Convert screenshot-local point to absolute screen point.
            abs_x = left + max(0, x)
            abs_y = top + max(0, y)

            mouse = get_provider(context, "pyautogui")
            mouse.click(abs_x, abs_y)
            title = str(out.get("title") or "")
            ev = []
            if title:
                ev.append(f"focused_window:{title}")
            ev.append(f"click_from_crop:{x},{y}->{abs_x},{abs_y}")
            ev.append(str(path))
            return ToolResult(success=True, data={"x": abs_x, "y": abs_y, "title": title}, evidence=ev)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = ["ClickCroppedScreenshotPointTool"]

