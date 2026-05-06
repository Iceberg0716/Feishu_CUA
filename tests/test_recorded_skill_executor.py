from __future__ import annotations

import unittest
from pathlib import Path

from runtime.context import RunContext
from runtime.recorded_skill_loader import RecordedSkillLoader
from runtime.recorded_skill_registry import RecordedSkillRegistry
from runtime.template_renderer import TemplateRenderer
from skills.recorded import RecordedSkillExecutor
from tools.base import BaseTool
from tools.registry import ToolRegistry
from tools.schema import ToolResult, ToolSpec


class _FakeTool(BaseTool):
    def __init__(self, name: str, handler) -> None:
        self.spec = ToolSpec(name=name, description=f"fake:{name}", input_schema={"type": "object"}, output_schema={"type": "object"})
        self._handler = handler

    def execute(self, params: dict, context: RunContext) -> ToolResult:  # noqa: ARG002
        return self._handler(params)


class TestTemplateRenderer(unittest.TestCase):
    def test_render_params(self) -> None:
        r = TemplateRenderer()
        out = r.render({"text": "Hello {{message}}"}, params={"message": "World"}, vars={})
        self.assertEqual(out["text"], "Hello World")

    def test_render_save_as_nested_index(self) -> None:
        r = TemplateRenderer()
        out = r.render("{{chat_candidate.click_point[0]}}", params={}, vars={"chat_candidate": {"click_point": [12, 34]}})
        self.assertEqual(out, 12)


class TestRecordedSkillExecutor(unittest.TestCase):
    def _load_registry(self) -> RecordedSkillRegistry:
        loader = RecordedSkillLoader()
        skills = loader.load_dir("recorded_skills")
        return RecordedSkillRegistry(skills)

    def _build_fake_tool_registry(self, call_log: list[tuple[str, dict]]) -> ToolRegistry:
        reg = ToolRegistry()

        def _ok(name: str, data=None):
            def _h(params: dict) -> ToolResult:
                call_log.append((name, dict(params)))
                return ToolResult(success=True, data=data or {}, evidence=[f"fake:{name}"])

            return _h

        def _screenshot(params: dict) -> ToolResult:
            call_log.append(("screen.screenshot", dict(params)))
            return ToolResult(success=True, data={"path": "fake_shot.png"}, evidence=["fake_shot.png"])

        def _find_chat(params: dict) -> ToolResult:
            call_log.append(("vlm.find_chat_candidate", dict(params)))
            return ToolResult(success=True, data={"click_point": [100, 200]}, evidence=["fake:vlm.find_chat_candidate"])

        def _judge_state(params: dict) -> ToolResult:
            call_log.append(("vlm.judge_state", dict(params)))
            return ToolResult(success=True, data={"success": True}, evidence=["fake:vlm.judge_state"])

        def _type_text(params: dict) -> ToolResult:
            call_log.append(("gui.type_text", dict(params)))
            if str(params.get("text")) == "FAIL":
                return ToolResult(success=False, error="fake type_text failed", evidence=["fake:fail"])
            return ToolResult(success=True, data={"len": len(str(params.get("text") or ""))}, evidence=["fake:gui.type_text"])

        reg.register(_FakeTool("gui.hotkey", _ok("gui.hotkey")))
        reg.register(_FakeTool("gui.focus_window", _ok("gui.focus_window")))
        reg.register(_FakeTool("gui.click", _ok("gui.click")))
        reg.register(_FakeTool("gui.click_cropped_screenshot_point", _ok("gui.click_cropped_screenshot_point")))
        reg.register(_FakeTool("gui.click_window_relative", _ok("gui.click_window_relative")))
        reg.register(_FakeTool("gui.type_text", _type_text))
        reg.register(_FakeTool("screen.screenshot", _screenshot))
        reg.register(_FakeTool("vlm.find_chat_candidate", _find_chat))
        reg.register(_FakeTool("vlm.judge_state", _judge_state))
        return reg

    def test_executor_calls_fake_tools_in_order(self) -> None:
        call_log: list[tuple[str, dict]] = []
        tools = self._build_fake_tool_registry(call_log)
        reg = self._load_registry()
        loader = RecordedSkillLoader()
        skill = loader.load_path("recorded_skills/im/open_chat_by_search.yaml")

        ctx = RunContext(run_id="t1", artifacts_dir=Path("artifacts/runs/t1"), tool_registry=tools)
        ex = RecordedSkillExecutor(tool_registry=tools, skill_registry=reg, sleep=lambda _: None)
        res = ex.execute(skill, params={"chat_name": "测试群"}, context=ctx)
        self.assertTrue(res.success)
        self.assertEqual([n for n, _ in call_log][:4], ["gui.focus_window", "gui.hotkey", "gui.hotkey", "gui.type_text"])

    def test_executor_end_step(self) -> None:
        call_log: list[tuple[str, dict]] = []
        tools = self._build_fake_tool_registry(call_log)
        reg = self._load_registry()
        loader = RecordedSkillLoader()
        skill = loader.load_path("recorded_skills/im/open_chat_by_search.yaml")

        ctx = RunContext(run_id="t2", artifacts_dir=Path("artifacts/runs/t2"), tool_registry=tools)
        ex = RecordedSkillExecutor(tool_registry=tools, skill_registry=reg, sleep=lambda _: None)
        res = ex.execute(skill, params={"chat_name": "测试群"}, context=ctx, end_step="s3_type_chat_name")
        self.assertTrue(res.success)
        self.assertEqual(len(call_log), 4)

    def test_executor_stops_on_failure(self) -> None:
        call_log: list[tuple[str, dict]] = []
        tools = self._build_fake_tool_registry(call_log)
        reg = self._load_registry()
        loader = RecordedSkillLoader()
        skill = loader.load_path("recorded_skills/im/open_chat_by_search.yaml")

        ctx = RunContext(run_id="t3", artifacts_dir=Path("artifacts/runs/t3"), tool_registry=tools)
        ex = RecordedSkillExecutor(tool_registry=tools, skill_registry=reg, sleep=lambda _: None)
        res = ex.execute(skill, params={"chat_name": "FAIL"}, context=ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.failed_step, "s3_type_chat_name")
        self.assertEqual([n for n, _ in call_log], ["gui.focus_window", "gui.hotkey", "gui.hotkey", "gui.type_text"])

    def test_composed_skill_executes_children_and_inherits_side_effect(self) -> None:
        call_log: list[tuple[str, dict]] = []
        tools = self._build_fake_tool_registry(call_log)
        reg = self._load_registry()
        loader = RecordedSkillLoader()
        composed = loader.load_path("recorded_skills/im/send_message_composed.yaml")

        ctx = RunContext(run_id="t4", artifacts_dir=Path("artifacts/runs/t4"), tool_registry=tools)
        ex = RecordedSkillExecutor(tool_registry=tools, skill_registry=reg, sleep=lambda _: None)
        res = ex.execute(composed, params={"chat_name": "测试群", "message": "Hello"}, context=ctx)
        self.assertTrue(res.success)
        shots = [p.get("filename") for n, p in call_log if n == "screen.screenshot"]
        self.assertIn("recorded_im_send_text_after.png", shots)
        self.assertTrue(RecordedSkillExecutor.compute_side_effect(composed, reg))


if __name__ == "__main__":
    unittest.main()
