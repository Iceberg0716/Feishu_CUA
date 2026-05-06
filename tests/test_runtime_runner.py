from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from runtime.runner import Runner
from skills.base import BaseSkill, SkillResult
from skills.registry import SkillRegistry
from tools.base import BaseTool
from tools.registry import ToolRegistry
from tools.schema import ToolResult, ToolSpec


class _FakeScreenshotTool(BaseTool):
    spec = ToolSpec(name="screen.screenshot", description="x", input_schema={}, output_schema={}, side_effect=True)

    def execute(self, params: dict, context):  # noqa: ANN001
        out = Path(context.artifacts_dir) / str(params.get("subdir", "screenshots")) / str(params["filename"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"png")
        return ToolResult(success=True, data={"path": str(out)}, evidence=[str(out)])


class _OkSkill(BaseSkill):
    name = "im.send_message"
    description = "x"
    input_schema = {}

    def execute(self, params, context):  # noqa: ANN001
        return SkillResult(success=True, data={"ok": True}, evidence=["skill:ok"])


class TestRunner(unittest.TestCase):
    def test_runner_creates_run_dir_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            tools = ToolRegistry()
            tools.register(_FakeScreenshotTool())
            skills = SkillRegistry()
            skills.register(_OkSkill())
            fixed = datetime(2026, 5, 3, 12, 0, 0)
            runner = Runner(
                config={"runtime": {"retry_times": 0}, "ocr": {"provider": "paddleocr", "language": "ch"}, "vlm": {"enabled": False}},
                artifacts_base=base,
                providers={},
                tool_registry=tools,
                skill_registry=skills,
                now=lambda: fixed,
            )
            # Write a testcase yaml so run_files covers file loading path.
            tc = base / "tc.yaml"
            tc.write_text(
                "id: im_send_message_001\nproduct: im\ninstruction: x\nparams:\n  chat_name: c\n  message: m\n",
                encoding="utf-8",
            )
            run = runner.run_files([str(tc)])
            self.assertTrue(run.cases[0].success)
            run_dir = base / "2026-05-03_120000"
            self.assertTrue((run_dir / "result.json").exists())
            self.assertTrue((run_dir / "screenshots").exists())


if __name__ == "__main__":
    unittest.main()
