from __future__ import annotations

import unittest
from pathlib import Path

from runtime.context import RunContext
from tools.gui.click import ClickTool
from tools.gui.focus_window import FocusWindowTool
from tools.gui.hotkey import HotkeyTool
from tools.gui.scroll import ScrollTool
from tools.gui.type_text import TypeTextTool
from tools.gui.wait import WaitTool


class _DummyPyAutoGUIProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def click(self, x: int, y: int, *, clicks: int = 1, interval: float = 0.0, button: str = "left") -> None:
        self.calls.append(("click", (x, y), {"clicks": clicks, "interval": interval, "button": button}))

    def type_text(self, text: str, *, interval: float = 0.0, replace: bool = False) -> None:
        self.calls.append(("type_text", (text,), {"interval": interval, "replace": replace}))

    def hotkey(self, *keys: str) -> None:
        self.calls.append(("hotkey", keys, {}))

    def press(self, key: str, *, presses: int = 1, interval: float = 0.0) -> None:
        self.calls.append(("press", (key,), {"presses": presses, "interval": interval}))

    def scroll(self, clicks: int, *, x: int | None = None, y: int | None = None) -> None:
        self.calls.append(("scroll", (clicks,), {"x": x, "y": y}))


class _DummyPywinautoProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def focus_window(self, title_keywords: list[str]) -> str:
        self.calls.append(("focus_window", (tuple(title_keywords),), {}))
        return "飞书 - 工作台"


def _ctx() -> RunContext:
    return RunContext(
        run_id="r1",
        artifacts_dir=Path("artifacts/runs/r1"),
        metadata={
            "providers": {
                "pyautogui": _DummyPyAutoGUIProvider(),
                "pywinauto": _DummyPywinautoProvider(),
            }
        },
    )


class TestGuiTools(unittest.TestCase):
    def test_focus_window_tool(self) -> None:
        ctx = _ctx()
        tool = FocusWindowTool()
        res = tool.execute({"title_keywords": ["飞书", "Feishu", "Lark"]}, ctx)
        self.assertTrue(res.success)
        self.assertIn("title", res.data)
        self.assertIn("飞书", res.data["title"])

    def test_click_tool(self) -> None:
        ctx = _ctx()
        tool = ClickTool()
        res = tool.execute({"x": 10, "y": 20, "clicks": 2}, ctx)
        self.assertTrue(res.success)

    def test_type_text_tool(self) -> None:
        ctx = _ctx()
        tool = TypeTextTool()
        res = tool.execute({"text": "hello", "interval": 0.01}, ctx)
        self.assertTrue(res.success)

    def test_hotkey_tool(self) -> None:
        ctx = _ctx()
        tool = HotkeyTool()
        res = tool.execute({"keys": ["ctrl", "k"]}, ctx)
        self.assertTrue(res.success)

    def test_hotkey_tool_single_key_uses_press(self) -> None:
        ctx = _ctx()
        tool = HotkeyTool()
        res = tool.execute({"keys": ["enter"]}, ctx)
        self.assertTrue(res.success)
        prov = ctx.metadata["providers"]["pyautogui"]
        self.assertTrue(any(c[0] == "press" for c in prov.calls))

    def test_scroll_tool(self) -> None:
        ctx = _ctx()
        tool = ScrollTool()
        res = tool.execute({"clicks": -100}, ctx)
        self.assertTrue(res.success)

    def test_wait_tool(self) -> None:
        ctx = _ctx()
        tool = WaitTool()
        res = tool.execute({"seconds": 0}, ctx)
        self.assertTrue(res.success)
        self.assertIn("wait_seconds:", " ".join(res.evidence))


if __name__ == "__main__":
    unittest.main()
