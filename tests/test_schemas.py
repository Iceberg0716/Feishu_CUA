from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from runtime.context import RunContext
from runtime.models import CaseResult, StepLog
from skills.base import SkillResult
from tools.schema import ToolResult, ToolSpec


class TestSchemas(unittest.TestCase):
    def test_tool_spec_roundtrip(self) -> None:
        spec = ToolSpec(
            name="gui.click",
            description="Click something",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            timeout=10,
            retryable=True,
            side_effect=True,
        )
        dumped = spec.model_dump()
        loaded = ToolSpec.model_validate(dumped)
        self.assertEqual(loaded, spec)

    def test_tool_result_roundtrip(self) -> None:
        result = ToolResult(
            success=False,
            error="boom",
            evidence=["a.png", "ocr:foo"],
            confidence=0.1,
            data={"k": "v"},
        )
        loaded = ToolResult.model_validate(result.model_dump())
        self.assertEqual(loaded, result)

    def test_skill_result_roundtrip(self) -> None:
        result = SkillResult(success=True, data={"x": 1}, evidence=["e1"])
        loaded = SkillResult.model_validate(result.model_dump())
        self.assertEqual(loaded, result)

    def test_run_models_roundtrip(self) -> None:
        now = datetime.now(timezone.utc)
        step = StepLog(
            step_id="s1",
            step_type="skill",
            name="im.send_message",
            params={"chat_name": "测试群"},
            success=True,
            started_at=now,
            ended_at=now,
            evidence=["before.png", "after.png"],
            result={"data": {"ok": True}},
        )
        case = CaseResult(
            case_id="im_send_message_001",
            goal="send message",
            success=True,
            started_at=now,
            ended_at=now,
            steps=[step],
        )
        loaded = CaseResult.model_validate(case.model_dump(mode="json"))
        self.assertEqual(loaded.case_id, case.case_id)
        self.assertEqual(loaded.steps[0].name, "im.send_message")

    def test_run_context_default_registry(self) -> None:
        ctx = RunContext(run_id="r1", artifacts_dir=Path("artifacts/runs/r1"))
        self.assertIsNotNone(ctx.tool_registry)


if __name__ == "__main__":
    unittest.main()

