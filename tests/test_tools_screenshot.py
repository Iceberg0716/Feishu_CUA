from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.context import RunContext
from tools.vision.screenshot import ScreenshotTool


class _DummyPyAutoGUIProvider:
    def __init__(self) -> None:
        self.screenshot_paths: list[str] = []

    def screenshot(self, path: str | Path) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"png")
        self.screenshot_paths.append(str(p))
        return str(p)


class TestScreenshotTool(unittest.TestCase):
    def test_screenshot_tool_writes_under_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ctx = RunContext(
                run_id="r1",
                artifacts_dir=Path(td) / "run",
                metadata={"providers": {"pyautogui": _DummyPyAutoGUIProvider()}},
            )
            tool = ScreenshotTool()
            res = tool.execute({"filename": "s1_before.png"}, ctx)
            self.assertTrue(res.success)
            self.assertTrue(Path(res.data["path"]).exists())
            self.assertIn("screenshots", Path(res.data["path"]).parts)


if __name__ == "__main__":
    unittest.main()

