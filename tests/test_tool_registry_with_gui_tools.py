from __future__ import annotations

import unittest

from tools.registry import ToolRegistry
from tools.gui.click import ClickTool
from tools.gui.click_window_relative import ClickWindowRelativeTool
from tools.gui.focus_window import FocusWindowTool
from tools.gui.hotkey import HotkeyTool
from tools.gui.scroll import ScrollTool
from tools.gui.type_text import TypeTextTool
from tools.gui.wait import WaitTool
from tools.vision.screenshot import ScreenshotTool


class TestToolRegistryWithGuiTools(unittest.TestCase):
    def test_register_and_list_specs(self) -> None:
        reg = ToolRegistry()
        reg.register(FocusWindowTool())
        reg.register(ClickTool())
        reg.register(ClickWindowRelativeTool())
        reg.register(TypeTextTool())
        reg.register(HotkeyTool())
        reg.register(ScrollTool())
        reg.register(WaitTool())
        reg.register(ScreenshotTool())
        names = {s.name for s in reg.list_specs()}
        self.assertIn("gui.focus_window", names)
        self.assertIn("gui.click", names)
        self.assertIn("gui.click_window_relative", names)
        self.assertIn("gui.type_text", names)
        self.assertIn("gui.hotkey", names)
        self.assertIn("gui.scroll", names)
        self.assertIn("gui.wait", names)
        self.assertIn("screen.screenshot", names)


if __name__ == "__main__":
    unittest.main()
