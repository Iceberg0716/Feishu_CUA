from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.context import RunContext
from tools.base import BaseTool
from tools.registry import ToolRegistry
from tools.schema import ToolResult, ToolSpec

from skills.app import OpenOrFocusSkill
from skills.im import SearchChatSkill, SendMessageSkill, SendTextSkill, VerifyMessageSkill


class _FakeTool(BaseTool):
    def __init__(self, name: str, *, result: ToolResult | None = None) -> None:
        self.calls: list[dict] = []
        self.spec = ToolSpec(name=name, description="fake", input_schema={}, output_schema={})
        self._result = result or ToolResult(success=True, data={})

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        self.calls.append({"params": params, "run_id": context.run_id})
        return self._result


def _ctx_with_tools(tools: dict[str, _FakeTool]) -> RunContext:
    reg = ToolRegistry()
    for tool in tools.values():
        reg.register(tool)
    return RunContext(
        run_id="r1",
        artifacts_dir=Path("artifacts/runs/r1"),
        tool_registry=reg,
        metadata={
            "config": {
                "app": {"feishu_window_title_keywords": ["飞书", "Feishu", "Lark"]},
                "im": {"message_input_x_ratio": 0.65, "message_input_y_ratio": 0.92},
            }
        },
    )


class TestAppOpenOrFocus(unittest.TestCase):
    def test_uses_config_keywords_by_default(self) -> None:
        focus = _FakeTool("gui.focus_window", result=ToolResult(success=True, data={"title": "Feishu - Work"}))
        ctx = _ctx_with_tools({"gui.focus_window": focus})
        res = OpenOrFocusSkill().execute({}, ctx)
        self.assertTrue(res.success)
        self.assertEqual(focus.calls[0]["params"]["title_keywords"], ["飞书", "Feishu", "Lark"])


class TestImSkills(unittest.TestCase):
    def test_search_chat_calls_hotkey_type_enter(self) -> None:
        hotkey = _FakeTool("gui.hotkey")
        typ = _FakeTool("gui.type_text")
        wait = _FakeTool("gui.wait")
        ctx = _ctx_with_tools({"gui.hotkey": hotkey, "gui.type_text": typ, "gui.wait": wait})
        res = SearchChatSkill().execute({"chat_name": "测试群"}, ctx)
        self.assertTrue(res.success)
        self.assertEqual(hotkey.calls[0]["params"]["keys"], ["ctrl", "k"])
        self.assertEqual(typ.calls[0]["params"]["text"], "测试群")
        keys = [c["params"]["keys"] for c in hotkey.calls]
        # ctrl+k -> ctrl+a -> enter (with waits in between)
        self.assertIn(["ctrl", "a"], keys)
        self.assertGreaterEqual(keys.count(["enter"]), 1)

    def test_send_text_types_message_and_enters(self) -> None:
        hotkey = _FakeTool("gui.hotkey")
        click_rel = _FakeTool("gui.click_window_relative")
        typ = _FakeTool("gui.type_text")
        wait = _FakeTool("gui.wait")
        ctx = _ctx_with_tools(
            {"gui.hotkey": hotkey, "gui.click_window_relative": click_rel, "gui.type_text": typ, "gui.wait": wait}
        )
        res = SendTextSkill().execute({"message": "Hello"}, ctx)
        self.assertTrue(res.success)
        self.assertEqual(typ.calls[0]["params"]["text"], "Hello")
        self.assertEqual(hotkey.calls[-1]["params"]["keys"], ["enter"])

    def test_verify_message_screenshots_then_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            img = str(Path(td) / "s.png")
            focus = _FakeTool("gui.focus_window", result=ToolResult(success=True, data={"title": "Feishu"}))
            shot = _FakeTool("screen.screenshot", result=ToolResult(success=True, data={"path": img}, evidence=[img]))
            verify = _FakeTool("verify.text_visible", result=ToolResult(success=True, data={"ok": True}))
            ctx = _ctx_with_tools({"gui.focus_window": focus, "screen.screenshot": shot, "verify.text_visible": verify})
            res = VerifyMessageSkill().execute({"text": "Hello"}, ctx)
            self.assertTrue(res.success)
            self.assertEqual(verify.calls[0]["params"]["path"], img)
            self.assertEqual(verify.calls[0]["params"]["text"], "Hello")

    def test_send_message_composes_subskills(self) -> None:
        focus = _FakeTool("gui.focus_window", result=ToolResult(success=True, data={"title": "Feishu"}))
        hotkey = _FakeTool("gui.hotkey")
        click_rel = _FakeTool("gui.click_window_relative")
        typ = _FakeTool("gui.type_text")
        wait = _FakeTool("gui.wait")
        shot = _FakeTool("screen.screenshot", result=ToolResult(success=True, data={"path": "a.png"}))
        verify = _FakeTool("verify.text_visible", result=ToolResult(success=True, data={"ok": True}))
        ctx = _ctx_with_tools(
            {
                "gui.focus_window": focus,
                "gui.hotkey": hotkey,
                "gui.click_window_relative": click_rel,
                "gui.type_text": typ,
                "gui.wait": wait,
                "screen.screenshot": shot,
                "verify.text_visible": verify,
            }
        )
        res = SendMessageSkill().execute({"chat_name": "测试群", "message": "Hello"}, ctx)
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
