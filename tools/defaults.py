from __future__ import annotations

from tools.gui.click import ClickTool
from tools.gui.click_window_relative import ClickWindowRelativeTool
from tools.gui.click_cropped_screenshot_point import ClickCroppedScreenshotPointTool
from tools.gui.focus_window import FocusWindowTool
from tools.gui.hotkey import HotkeyTool
from tools.gui.scroll import ScrollTool
from tools.gui.type_text import TypeTextTool
from tools.gui.wait import WaitTool
from tools.semantic.vlm_find_chat_candidate import VlmFindChatCandidateTool
from tools.registry import ToolRegistry
from tools.semantic.vlm_judge_state import VlmJudgeStateTool
from tools.verify.text_visible import TextVisibleTool
from tools.vision.screenshot import ScreenshotTool


def _vision_ocr_enabled(config: dict | None) -> bool:
    if not isinstance(config, dict):
        return True
    vision = config.get("vision")
    if isinstance(vision, dict) and "ocr_enabled" in vision:
        return bool(vision.get("ocr_enabled"))
    ocr = config.get("ocr")
    if isinstance(ocr, dict) and "enabled" in ocr:
        return bool(ocr.get("enabled"))
    return True


def build_default_tool_registry(config: dict | None = None) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(FocusWindowTool())
    reg.register(ClickTool())
    reg.register(ClickWindowRelativeTool())
    reg.register(ClickCroppedScreenshotPointTool())
    reg.register(TypeTextTool())
    reg.register(HotkeyTool())
    reg.register(ScrollTool())
    reg.register(WaitTool())
    reg.register(ScreenshotTool())
    reg.register(TextVisibleTool())
    reg.register(VlmJudgeStateTool())
    reg.register(VlmFindChatCandidateTool())
    if _vision_ocr_enabled(config):
        # Only register OCR tools when OCR is enabled; otherwise any attempt to
        # call them should fail fast with "tool missing" and never touch PaddleOCR.
        from tools.vision.locate_text import LocateTextTool
        from tools.vision.ocr_extract import OcrExtractTool

        reg.register(OcrExtractTool())
        reg.register(LocateTextTool())
    return reg


__all__ = ["build_default_tool_registry"]
