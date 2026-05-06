from __future__ import annotations

import json
import unittest

from agent.llm_planner import LLMPlanner
from runtime.recorded_skill_loader import RecordedSkillLoader
from runtime.recorded_skill_registry import RecordedSkillRegistry


class _FakeLLM:
    def __init__(self, *, response_json: dict) -> None:
        self._response = json.dumps(response_json, ensure_ascii=False)

    def chat_json(self, *, system_prompt: str, user_prompt: str, timeout_seconds: int = 30) -> str:  # noqa: ARG002
        return self._response


class TestLLMPlanner(unittest.TestCase):
    def _registry(self) -> RecordedSkillRegistry:
        loader = RecordedSkillLoader()
        skills = loader.load_dir("recorded_skills")
        return RecordedSkillRegistry(skills)

    def test_send_helloworld_plans_open_chat_then_send_text(self) -> None:
        reg = self._registry()
        fake = _FakeLLM(
            response_json={
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
        )
        planner = LLMPlanner(llm=fake)
        plan = planner.plan(instruction="在测试群里发送 HelloWorld", registry=reg)
        self.assertEqual(plan.status, "ok")
        self.assertEqual(plan.product, "im")
        self.assertEqual(plan.intent, "send_message")
        self.assertEqual(len(plan.subgoals), 2)
        self.assertEqual(plan.subgoals[0].intent, "open_chat")
        self.assertEqual(plan.subgoals[1].intent, "send_text")

    def test_mention_member_plans_open_chat_then_mention_member(self) -> None:
        reg = self._registry()
        fake = _FakeLLM(
            response_json={
                "status": "ok",
                "product": "im",
                "intent": "mention_member",
                "params": {"chat_name": "测试群", "member_name": "马烨", "message": "请看一下"},
                "subgoals": [
                    {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
                    {"product": "im", "intent": "mention_member", "params": {"member_name": "马烨", "message": "请看一下"}},
                ],
                "confidence": 0.92,
            }
        )
        planner = LLMPlanner(llm=fake)
        plan = planner.plan(instruction="在测试群里@马烨说请看一下", registry=reg)
        self.assertEqual(plan.status, "ok")
        self.assertEqual(plan.product, "im")
        self.assertEqual(plan.intent, "mention_member")
        self.assertEqual(len(plan.subgoals), 2)
        self.assertEqual(plan.subgoals[0].intent, "open_chat")
        self.assertEqual(plan.subgoals[1].intent, "mention_member")

    def test_stepwise_intent_parse(self) -> None:
        reg = self._registry()
        fake = _FakeLLM(
            response_json={
                "status": "ok",
                "product": "im",
                "intent": "send_message",
                "params": {"chat_name": "测试群", "message": "HelloWorld"},
                "confidence": 0.88,
            }
        )
        planner = LLMPlanner(llm=fake)
        task = planner.plan_intent(instruction="在测试群里发送 HelloWorld", registry=reg)
        self.assertEqual(task.status, "ok")
        self.assertEqual(task.product, "im")
        self.assertEqual(task.intent, "send_message")
        self.assertEqual(task.params.get("chat_name"), "测试群")
        self.assertEqual(task.params.get("message"), "HelloWorld")

    def test_stepwise_next_subgoal_parse(self) -> None:
        reg = self._registry()
        fake = _FakeLLM(
            response_json={
                "status": "ok",
                "subgoal": {"product": "im", "intent": "open_chat", "params": {"chat_name": "测试群"}},
                "confidence": 0.9,
            }
        )
        planner = LLMPlanner(llm=fake)
        nxt = planner.plan_next_subgoal(
            instruction="在测试群里发送 HelloWorld",
            registry=reg,
            required_product="im",
            required_intent="open_chat",
            known_params={"chat_name": "测试群", "message": "HelloWorld"},
            current_state=["feishu_window_available"],
            last_step=None,
        )
        self.assertEqual(nxt.status, "ok")
        self.assertIsNotNone(nxt.subgoal)
        assert nxt.subgoal is not None
        self.assertEqual(nxt.subgoal.product, "im")
        self.assertEqual(nxt.subgoal.intent, "open_chat")
        self.assertEqual(nxt.subgoal.params.get("chat_name"), "测试群")


if __name__ == "__main__":
    unittest.main()
