from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.context import RunContext
from tools.registry import ToolRegistry
from tools.semantic.vlm_find_chat_candidate import VlmFindChatCandidateTool


class _DummyVlmProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def find_chat_candidate(  # noqa: ANN401
        self,
        image_path: str | Path,
        *,
        chat_name: str,
        search_box_max_y: int | None = None,
        timeout_seconds: int = 30,
    ) -> dict:
        self.calls.append(
            {
                "image_path": str(image_path),
                "chat_name": chat_name,
                "search_box_max_y": search_box_max_y,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"success": True, "bbox": [1, 2, 3, 4], "click_point": [5, 6], "reason": "ok", "evidence": ["vlm:ok"]}


class TestVlmFindChatCandidateTool(unittest.TestCase):
    def test_calls_provider_and_returns_toolresult(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            img = root / "a.png"
            img.write_bytes(b"png")
            reg = ToolRegistry()
            reg.register(VlmFindChatCandidateTool())
            ctx = RunContext(run_id="r1", artifacts_dir=root, tool_registry=reg, metadata={"providers": {"vlm": _DummyVlmProvider()}})
            res = reg.get("vlm.find_chat_candidate").execute({"path": str(img), "chat_name": "马烨", "search_box_max_y": 123}, ctx)
            self.assertTrue(res.success)
            self.assertEqual(res.data["bbox"], [1, 2, 3, 4])
            self.assertEqual(res.data["click_point"], [5, 6])
            self.assertIn("vlm:ok", res.evidence)


if __name__ == "__main__":
    unittest.main()

