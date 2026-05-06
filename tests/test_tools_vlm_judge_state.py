from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.context import RunContext
from tools.registry import ToolRegistry
from tools.semantic.vlm_judge_state import VlmJudgeStateTool


class _DummyVlmProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def judge_state(self, image_path: str | Path, *, expectation: str, timeout_seconds: int = 30) -> dict:  # noqa: ANN401
        self.calls.append({"image_path": str(image_path), "expectation": expectation, "timeout_seconds": timeout_seconds})
        return {"success": True, "confidence": 0.91, "reason": "ok", "evidence": ["vlm:ok"]}


class TestVlmJudgeStateTool(unittest.TestCase):
    def test_calls_provider_and_returns_toolresult(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            img = root / "a.png"
            img.write_bytes(b"png")
            reg = ToolRegistry()
            reg.register(VlmJudgeStateTool())
            ctx = RunContext(run_id="r1", artifacts_dir=root, tool_registry=reg, metadata={"providers": {"vlm": _DummyVlmProvider()}})
            res = reg.get("vlm.judge_state").execute({"path": str(img), "expectation": "x"}, ctx)
            self.assertTrue(res.success)
            self.assertAlmostEqual(res.confidence or 0.0, 0.91, places=2)
            self.assertIn("vlm:ok", res.evidence)


if __name__ == "__main__":
    unittest.main()

