from __future__ import annotations

from tools.gui.click import ClickTool
from tools.gui.click_window_relative import ClickWindowRelativeTool
from tools.gui.focus_window import FocusWindowTool
from tools.gui.hotkey import HotkeyTool
from tools.gui.scroll import ScrollTool
from tools.gui.type_text import TypeTextTool
from tools.gui.wait import WaitTool
from tools.registry import ToolRegistry
from tools.semantic.vlm_judge_state import VlmJudgeStateTool
from tools.verify.text_visible import TextVisibleTool
from tools.vision.locate_text import LocateTextTool
from tools.vision.ocr_extract import OcrExtractTool
from tools.vision.screenshot import ScreenshotTool


def build_default_tool_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(FocusWindowTool())
    reg.register(ClickTool())
    reg.register(ClickWindowRelativeTool())
    reg.register(TypeTextTool())
    reg.register(HotkeyTool())
    reg.register(ScrollTool())
    reg.register(WaitTool())
    reg.register(ScreenshotTool())
    reg.register(OcrExtractTool())
    reg.register(LocateTextTool())
    reg.register(TextVisibleTool())
    reg.register(VlmJudgeStateTool())
    return reg


__all__ = ["build_default_tool_registry"]
