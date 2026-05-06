from __future__ import annotations

from pathlib import Path

from runtime.context import RunContext
from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec


class ScreenshotTool(BaseTool):
    spec = ToolSpec(
        name="screen.screenshot",
        description="Take a screenshot and save under artifacts (optionally crop to app window).",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "subdir": {"type": "string"},
                "title_keywords": {"type": "array", "items": {"type": "string"}},
                "crop_to_window": {"type": "boolean"},
            },
            "required": ["filename"],
        },
        output_schema={"type": "object"},
        timeout=30,
        retryable=True,
        side_effect=True,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            filename = str(params["filename"])
            subdir = str(params.get("subdir", "screenshots"))
            out = (Path(context.artifacts_dir) / subdir / filename).resolve()
            crop_to_window = bool(params.get("crop_to_window", False))
            title_keywords = params.get("title_keywords")
            evidence: list[str] = []

            if crop_to_window or title_keywords:
                if not isinstance(title_keywords, list) or not title_keywords:
                    raise ValueError("title_keywords must be a non-empty list when cropping to window")
                win = get_provider(context, "pywinauto")
                out_win = win.focus_window_and_get_rect([str(k) for k in title_keywords])
                rect = out_win.get("rect") if isinstance(out_win, dict) else None
                if not isinstance(rect, dict):
                    raise ValueError("window rect missing")
                left = int(rect.get("left", 0))
                top = int(rect.get("top", 0))
                right = int(rect.get("right", 0))
                bottom = int(rect.get("bottom", 0))
                w = max(1, right - left)
                h = max(1, bottom - top)
                mouse = get_provider(context, "pyautogui")
                saved = mouse.screenshot_region(out, left=left, top=top, width=w, height=h)
                title = str(out_win.get("title") or "")
                if title:
                    evidence.append(f"focused_window:{title}")
                evidence.append(f"screenshot_crop:{left},{top},{w},{h}")
                evidence.append(saved)
                return ToolResult(success=True, data={"path": saved, "cropped": True}, evidence=evidence)

            provider = get_provider(context, "pyautogui")
            saved = provider.screenshot(out)
            return ToolResult(success=True, data={"path": saved, "cropped": False}, evidence=[saved])
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
