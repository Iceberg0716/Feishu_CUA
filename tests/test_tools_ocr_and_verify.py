from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.context import RunContext
from tools.vision.ocr_extract import OcrExtractTool
from tools.vision.locate_text import LocateTextTool
from tools.verify.text_visible import TextVisibleTool


class _DummyOcrProvider:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.calls: list[str] = []

    def extract_text(self, image_path: str | Path) -> list[dict]:
        self.calls.append(str(image_path))
        return self.items


class TestOcrAndVerifyTools(unittest.TestCase):
    def test_ocr_extract_tool_reads_relative_paths_under_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            img_rel = Path("screenshots") / "s1.png"
            img_abs = root / img_rel
            img_abs.parent.mkdir(parents=True, exist_ok=True)
            img_abs.write_bytes(b"png")

            provider = _DummyOcrProvider([{"text": "Hello", "confidence": 0.9, "bbox": [0, 0, 1, 1]}])
            ctx = RunContext(run_id="r1", artifacts_dir=root, metadata={"providers": {"ocr": provider}})
            tool = OcrExtractTool()
            res = tool.execute({"path": str(img_rel)}, ctx)
            self.assertTrue(res.success)
            self.assertEqual(res.data["items"][0]["text"], "Hello")
            self.assertIn(str(img_abs), provider.calls[0])

    def test_locate_text_tool_finds_matches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            img = root / "a.png"
            img.write_bytes(b"png")
            provider = _DummyOcrProvider(
                [
                    {"text": "Hello World", "confidence": 0.95, "bbox": [10, 20, 110, 60]},
                    {"text": "Other", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
                ]
            )
            ctx = RunContext(run_id="r1", artifacts_dir=root, metadata={"providers": {"ocr": provider}})
            tool = LocateTextTool()
            res = tool.execute({"path": str(img), "text": "World"}, ctx)
            self.assertTrue(res.success)
            self.assertTrue(res.data["found"])
            self.assertEqual(res.data["matches"][0]["center"], [60, 40])

    def test_text_visible_tool_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            img = root / "a.png"
            img.write_bytes(b"png")

            ctx_ok = RunContext(
                run_id="r1",
                artifacts_dir=root,
                metadata={"providers": {"ocr": _DummyOcrProvider([{"text": "abc DEF", "confidence": 0.9}])}},
            )
            ok = TextVisibleTool().execute({"path": str(img), "text": "def"}, ctx_ok)
            self.assertTrue(ok.success)

            ctx_no = RunContext(
                run_id="r1",
                artifacts_dir=root,
                metadata={"providers": {"ocr": _DummyOcrProvider([{"text": "abc", "confidence": 0.9}])}},
            )
            no = TextVisibleTool().execute({"path": str(img), "text": "zzz"}, ctx_no)
            self.assertFalse(no.success)

    def test_text_visible_tool_falls_back_to_vlm_on_ocr_error(self) -> None:
        class _BoomOcrProvider:
            def extract_text(self, image_path: str | Path) -> list[dict]:  # noqa: ANN001
                raise RuntimeError("ocr boom")

        class _FakeVlmProvider:
            def judge_state(self, image_path: str | Path, *, expectation: str, timeout_seconds: int = 30) -> dict:  # noqa: ANN001
                return {"success": True, "confidence": 0.9, "reason": "ok", "evidence": ["vlm_reason:ok"]}

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            img = root / "a.png"
            img.write_bytes(b"png")
            ctx = RunContext(
                run_id="r1",
                artifacts_dir=root,
                metadata={"providers": {"ocr": _BoomOcrProvider(), "vlm": _FakeVlmProvider()}},
            )
            res = TextVisibleTool().execute({"path": str(img), "text": "anything"}, ctx)
            self.assertTrue(res.success)
            self.assertEqual(res.data["method"], "vlm")


if __name__ == "__main__":
    unittest.main()
