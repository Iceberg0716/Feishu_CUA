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
    def test_search_chat_uses_ocr_vlm_click_strategy(self) -> None:
        focus = _FakeTool("gui.focus_window", result=ToolResult(success=True, data={"title": "Feishu"}))
        hotkey = _FakeTool("gui.hotkey")
        typ = _FakeTool("gui.type_text")
        wait = _FakeTool("gui.wait")
        shot = _FakeTool(
            "screen.screenshot",
            result=ToolResult(
                success=True,
                data={"path": "a.png", "cropped": True},
                evidence=["focused_window:Feishu", "screenshot_crop:0,0,1000,800", "a.png"],
            ),
        )
        ocr = _FakeTool(
            "vision.ocr_extract",
            result=ToolResult(
                success=True,
                data={
                    "path": "a.png",
                    "items": [
                        {"text": "测试群", "bbox": [100, 20, 150, 40], "confidence": 0.99},
                        {"text": "联系人", "bbox": [50, 120, 90, 140], "confidence": 0.9},
                        {"text": "测试群", "bbox": [220, 220, 300, 245], "confidence": 0.95},
                    ],
                },
            ),
        )
        click = _FakeTool("gui.click", result=ToolResult(success=True, data={"x": 140, "y": 232}, evidence=["click:140,232"]))
        judge = _FakeTool("vlm.judge_state", result=ToolResult(success=True, data={"reason": "ok"}, evidence=["vlm:ok"]))
        ctx = _ctx_with_tools(
            {
                "gui.focus_window": focus,
                "gui.hotkey": hotkey,
                "gui.type_text": typ,
                "gui.wait": wait,
                "screen.screenshot": shot,
                "vision.ocr_extract": ocr,
                "gui.click": click,
                "vlm.judge_state": judge,
            }
        )
        res = SearchChatSkill().execute({"chat_name": "测试群"}, ctx)
        self.assertTrue(res.success)
        self.assertIn("open_strategy:ocr_vlm_click", res.evidence)
        self.assertEqual(hotkey.calls[0]["params"]["keys"], ["ctrl", "k"])
        self.assertEqual(hotkey.calls[1]["params"]["keys"], ["ctrl", "a"])
        self.assertEqual(typ.calls[0]["params"]["text"], "测试群")
        self.assertGreaterEqual(len(click.calls), 1)
        self.assertEqual(click.calls[0]["params"]["x"], 140)
        self.assertEqual(click.calls[0]["params"]["y"], 232)
        keys = [c["params"]["keys"] for c in hotkey.calls]
        self.assertIn(["ctrl", "a"], keys)
        self.assertNotIn(["enter"], keys)

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
        shot = _FakeTool(
            "screen.screenshot",
            result=ToolResult(
                success=True,
                data={"path": "a.png", "cropped": True},
                evidence=["focused_window:Feishu", "screenshot_crop:0,0,1000,800", "a.png"],
            ),
        )
        ocr = _FakeTool(
            "vision.ocr_extract",
            result=ToolResult(
                success=True,
                data={
                    "path": "a.png",
                    "items": [
                        {"text": "联系人", "bbox": [50, 120, 90, 140], "confidence": 0.9},
                        {"text": "测试群", "bbox": [220, 220, 300, 245], "confidence": 0.95},
                    ],
                },
            ),
        )
        click = _FakeTool("gui.click", result=ToolResult(success=True, data={"x": 140, "y": 232}, evidence=["click:140,232"]))
        judge = _FakeTool("vlm.judge_state", result=ToolResult(success=True, data={"reason": "ok"}, evidence=["vlm:ok"]))
        verify = _FakeTool("verify.text_visible", result=ToolResult(success=True, data={"ok": True}))
        ctx = _ctx_with_tools(
            {
                "gui.focus_window": focus,
                "gui.hotkey": hotkey,
                "gui.click_window_relative": click_rel,
                "gui.type_text": typ,
                "gui.wait": wait,
                "screen.screenshot": shot,
                "vision.ocr_extract": ocr,
                "gui.click": click,
                "vlm.judge_state": judge,
                "verify.text_visible": verify,
            }
        )
        res = SendMessageSkill().execute({"chat_name": "测试群", "message": "Hello"}, ctx)
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
