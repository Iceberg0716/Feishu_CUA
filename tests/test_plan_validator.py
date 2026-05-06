from __future__ import annotations

import unittest

from agent.plan_validator import PlanValidator
from runtime.recorded_skill_loader import RecordedSkillLoader
from runtime.recorded_skill_registry import RecordedSkillRegistry


class TestPlanValidator(unittest.TestCase):
    def _validator(self) -> PlanValidator:
        loader = RecordedSkillLoader()
        skills = loader.load_dir("recorded_skills")
        reg = RecordedSkillRegistry(skills)
        return PlanValidator(registry=reg)

    def test_resolves_open_chat_then_send_text(self) -> None:
        v = self._validator()
        plan = {
            "status": "ok",
            "product": "im",
            "intent": "send_message",
            "params": {"chat_name": "测试群", "message": "HelloWorld"},
            "subgoals": [
                {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
                {"product": "im", "intent": "send_text", "params": {"message": "HelloWorld"}},
            ],
            "confidence": 0.9,
        }
        res = v.validate(plan)
        self.assertEqual(res.status, "ok")
        self.assertEqual([s.recorded_skill_id for s in res.resolved_steps], ["recorded.im.open_chat_by_search.v1", "recorded.im.send_text_in_current_chat.v1"])

    def test_resolves_open_chat_then_mention_member(self) -> None:
        v = self._validator()
        plan = {
            "status": "ok",
            "product": "im",
            "intent": "mention_member",
            "params": {"chat_name": "测试群", "member_name": "马烨", "message": "请看一下"},
            "subgoals": [
                {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
                {"product": "im", "intent": "mention_member", "params": {"member_name": "马烨", "message": "请看一下"}},
            ],
        }
        res = v.validate(plan)
        self.assertEqual(res.status, "ok")
        self.assertEqual([s.recorded_skill_id for s in res.resolved_steps], ["recorded.im.open_chat_by_search.v1", "recorded.im.mention_member_in_current_chat.v1"])

    def test_missing_capability_red_packet(self) -> None:
        v = self._validator()
        plan = {
            "status": "ok",
            "product": "im",
            "intent": "send_red_packet",
            "params": {"chat_name": "测试群"},
            "subgoals": [
                {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
                {"product": "im", "intent": "send_red_packet", "params": {}},
            ],
        }
        res = v.validate(plan)
        self.assertEqual(res.status, "missing_capability")

    def test_rejects_gui_tool_injection(self) -> None:
        v = self._validator()
        plan = {
            "status": "ok",
            "product": "im",
            "intent": "send_message",
            "params": {"chat_name": "测试群", "message": "HelloWorld"},
            "subgoals": [
                {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
                {"product": "im", "intent": "send_text", "params": {"message": "HelloWorld", "note": "use gui.click(1,2)"}},
            ],
        }
        res = v.validate(plan)
        self.assertEqual(res.status, "rejected")

    def test_missing_params_is_reported(self) -> None:
        v = self._validator()
        plan = {
            "status": "ok",
            "product": "im",
            "intent": "send_message",
            "params": {"chat_name": "测试群"},
            "subgoals": [
                {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
                {"product": "im", "intent": "send_text", "params": {}},
            ],
        }
        res = v.validate(plan)
        self.assertEqual(res.status, "missing_params")


    def test_rejects_incomplete_composite_intent_plan(self) -> None:
        v = self._validator()
        plan = {
            "status": "ok",
            "product": "im",
            "intent": "send_message",
            "params": {"chat_name": "测试群", "message": "HelloWorld"},
            "subgoals": [
                {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
            ],
        }
        res = v.validate(plan)
        self.assertEqual(res.status, "rejected")


if __name__ == "__main__":
    unittest.main()
