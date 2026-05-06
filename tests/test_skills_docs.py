from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.context import RunContext
from tools.base import BaseTool
from tools.registry import ToolRegistry
from tools.schema import ToolResult, ToolSpec

from skills.docs import CreateDocumentSkill, OpenDocsHomeSkill, VerifyDocumentSkill


class _FakeTool(BaseTool):
    def __init__(self, name: str, *, result: ToolResult | None = None) -> None:
        self.calls: list[dict] = []
        self.spec = ToolSpec(name=name, description="fake", input_schema={}, output_schema={})
        self._result = result or ToolResult(success=True, data={})

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        self.calls.append({"params": params})
        return self._result


def _ctx(tools: dict[str, _FakeTool]) -> RunContext:
    reg = ToolRegistry()
    for t in tools.values():
        reg.register(t)
    return RunContext(
        run_id="r1",
        artifacts_dir=Path("artifacts/runs/r1"),
        tool_registry=reg,
        metadata={
            "config": {
                "app": {"feishu_window_title_keywords": ["飞书", "Feishu", "Lark"]},
                "docs": {"home_entry_keyword": "云文档", "new_doc_hotkey": ["ctrl", "n"]},
            }
        },
    )


class TestDocsSkills(unittest.TestCase):
    def test_open_docs_home_uses_config_keyword(self) -> None:
        focus = _FakeTool("gui.focus_window", result=ToolResult(success=True, data={"title": "Feishu"}))
        hotkey = _FakeTool("gui.hotkey")
        typ = _FakeTool("gui.type_text")
        wait = _FakeTool("gui.wait")
        ctx = _ctx({"gui.focus_window": focus, "gui.hotkey": hotkey, "gui.type_text": typ, "gui.wait": wait})
        res = OpenDocsHomeSkill().execute({}, ctx)
        self.assertTrue(res.success)
        self.assertEqual(hotkey.calls[0]["params"]["keys"], ["ctrl", "k"])
        self.assertEqual(typ.calls[0]["params"]["text"], "云文档")

    def test_verify_document_checks_all_texts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            img = str(Path(td) / "s.png")
            focus = _FakeTool("gui.focus_window", result=ToolResult(success=True, data={"title": "Feishu"}))
            shot = _FakeTool("screen.screenshot", result=ToolResult(success=True, data={"path": img}, evidence=[img]))
            verify = _FakeTool("verify.text_visible", result=ToolResult(success=True, data={"ok": True}))
            ctx = _ctx({"gui.focus_window": focus, "screen.screenshot": shot, "verify.text_visible": verify})
            res = VerifyDocumentSkill().execute({"texts": ["A", "B"]}, ctx)
            self.assertTrue(res.success)
            self.assertEqual(len(verify.calls), 2)
            self.assertEqual(verify.calls[0]["params"]["path"], img)
            self.assertEqual(verify.calls[1]["params"]["text"], "B")

    def test_create_document_composes(self) -> None:
        focus = _FakeTool("gui.focus_window", result=ToolResult(success=True, data={"title": "Feishu"}))
        hotkey = _FakeTool("gui.hotkey")
        typ = _FakeTool("gui.type_text")
        wait = _FakeTool("gui.wait")
        shot = _FakeTool("screen.screenshot", result=ToolResult(success=True, data={"path": "a.png"}))
        verify = _FakeTool("verify.text_visible", result=ToolResult(success=True, data={"ok": True}))
        ctx = _ctx(
            {
                "gui.focus_window": focus,
                "gui.hotkey": hotkey,
                "gui.type_text": typ,
                "gui.wait": wait,
                "screen.screenshot": shot,
                "verify.text_visible": verify,
            }
        )
        res = CreateDocumentSkill().execute({"doc_name": "项目周报", "title": "T1", "body": "B"}, ctx)
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
