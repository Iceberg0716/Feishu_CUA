from __future__ import annotations

import unittest

from runtime.recorded_planner import RecordedPlanner
from runtime.recorded_skill_loader import RecordedSkillLoader
from runtime.recorded_skill_registry import RecordedSkillRegistry


class TestRecordedPlanner(unittest.TestCase):
    def _planner(self) -> RecordedPlanner:
        loader = RecordedSkillLoader()
        skills = loader.load_dir("recorded_skills")
        reg = RecordedSkillRegistry(skills)
        return RecordedPlanner(registry=reg)

    def test_send_message_splits_into_open_chat_and_send_text(self) -> None:
        planner = self._planner()
        plan = planner.plan(
            product="im",
            intent="send_message",
            params={"chat_name": "测试群", "message": "Hello"},
            current_state=["feishu_window_available"],
        )
        self.assertTrue(plan.complete)
        self.assertEqual(len(plan.steps), 2)

        s1 = plan.steps[0]
        self.assertEqual(s1.type, "recorded_skill")
        self.assertEqual(s1.recorded_skill_id, "recorded.im.open_chat_by_search.v1")

        s2 = plan.steps[1]
        self.assertEqual(s2.type, "recorded_skill")
        self.assertEqual(s2.recorded_skill_id, "recorded.im.send_text_in_current_chat.v1")

    def test_send_emoji_reuses_open_chat_then_missing(self) -> None:
        planner = self._planner()
        plan = planner.plan(
            product="im",
            intent="send_emoji",
            params={"chat_name": "测试群", "emoji_name": "笑脸"},
            current_state=["feishu_window_available"],
        )
        self.assertFalse(plan.complete)
        self.assertEqual(len(plan.steps), 2)

        s1 = plan.steps[0]
        self.assertEqual(s1.type, "recorded_skill")
        self.assertEqual(s1.recorded_skill_id, "recorded.im.open_chat_by_search.v1")

        s2 = plan.steps[1]
        self.assertEqual(s2.type, "missing_capability")
        self.assertEqual(s2.intent, "send_emoji")
        self.assertEqual(s2.suggested_recorded_skill_id, "recorded.im.send_emoji_in_current_chat.v1")
        self.assertIn("active_chat_opened", s2.current_state)

    def test_mention_member_splits_into_open_chat_and_mention_member(self) -> None:
        planner = self._planner()
        plan = planner.plan(
            product="im",
            intent="mention_member",
            params={"chat_name": "测试群", "member_name": "张三", "message": "请看一下"},
            current_state=["feishu_window_available"],
        )
        self.assertTrue(plan.complete)
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].type, "recorded_skill")
        self.assertEqual(plan.steps[0].recorded_skill_id, "recorded.im.open_chat_by_search.v1")
        self.assertEqual(plan.steps[1].type, "recorded_skill")
        self.assertEqual(plan.steps[1].recorded_skill_id, "recorded.im.mention_member_in_current_chat.v1")

    def test_mention_member_missing_params_returns_clear_error(self) -> None:
        planner = self._planner()
        plan = planner.plan(
            product="im",
            intent="mention_member",
            params={"chat_name": "测试群", "member_name": "张三"},
            current_state=["feishu_window_available"],
        )
        self.assertFalse(plan.complete)
        self.assertEqual(len(plan.steps), 2)
        missing = plan.steps[1]
        self.assertEqual(missing.type, "missing_capability")
        self.assertEqual(missing.intent, "mention_member")
        self.assertEqual(missing.missing_reason_code, "missing_params")
        self.assertIn("message", missing.missing_reason)

    def test_cli_recorded_plan_does_not_build_tool_registry(self) -> None:
        from runtime import cli as cli_mod
        import io
        from contextlib import redirect_stdout

        orig = cli_mod.build_default_tool_registry
        cli_mod.build_default_tool_registry = lambda _cfg: (_ for _ in ()).throw(AssertionError("should not be called"))
        try:
            with redirect_stdout(io.StringIO()):
                rc = cli_mod.cmd_recorded_plan(
                    "im",
                    "send_emoji",
                    raw_params=["chat_name=测试群", "emoji_name=笑脸"],
                    raw_state=["feishu_window_available"],
                    config_path="config.yaml",
                )
            self.assertEqual(rc, 1)
        finally:
            cli_mod.build_default_tool_registry = orig


if __name__ == "__main__":
    unittest.main()
