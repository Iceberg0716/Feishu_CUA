from __future__ import annotations

from typing import Any

from agent.schemas import Plan, PlanStep


class RulePlanner:
    def build_plan(self, testcase: dict[str, Any]) -> Plan:
        case_id = str(testcase.get("id") or "")
        if not case_id:
            raise ValueError("testcase.id is required")
        instruction = str(testcase.get("instruction") or "")
        product = str(testcase.get("product") or "").lower()
        params = testcase.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        goal = instruction or f"Run testcase {case_id}"

        if product == "im" or ("IM" in instruction and "发送" in instruction):
            step = PlanStep(
                id="s1",
                type="skill",
                name="im.send_message",
                params={"chat_name": params.get("chat_name"), "message": params.get("message")},
                expect=testcase.get("expected"),
            )
            return Plan(case_id=case_id, goal=goal, steps=[step])

        if product == "docs" or ("文档" in instruction and "创建" in instruction):
            step = PlanStep(
                id="s1",
                type="skill",
                name="docs.create_document",
                params={"doc_name": params.get("doc_name"), "title": params.get("title"), "body": params.get("body")},
                expect=testcase.get("expected"),
            )
            return Plan(case_id=case_id, goal=goal, steps=[step])

        raise ValueError(f"unsupported testcase product/instruction: product={product!r}")


__all__ = ["RulePlanner"]

