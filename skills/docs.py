from __future__ import annotations

from datetime import datetime
from typing import Any

from runtime.context import RunContext
from skills._helpers import config_get, tool_call
from skills.app import OpenOrFocusSkill
from skills.base import BaseSkill, SkillResult


class OpenDocsHomeSkill(BaseSkill):
    name = "docs.open_home"
    description = "Open Feishu Docs home."
    side_effect = False
    input_schema: dict[str, Any] = {"type": "object", "properties": {"entry_keyword": {"type": "string"}}}

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        evidence: list[str] = []
        try:
            app_res = OpenOrFocusSkill().execute({}, context)
            evidence += app_res.evidence
            if not app_res.success:
                return SkillResult(success=False, error=app_res.error or "app.open_or_focus failed", evidence=evidence)

            keyword = params.get("entry_keyword")
            if keyword is None:
                keyword = config_get(context, "docs.home_entry_keyword", "云文档")
            keyword = str(keyword)

            hk1 = tool_call(context, "gui.hotkey", {"keys": ["ctrl", "k"]})
            evidence += hk1.evidence
            if not hk1.success:
                return SkillResult(success=False, error=hk1.error or "gui.hotkey failed", evidence=evidence)

            wt0 = tool_call(context, "gui.wait", {"seconds": 0.1})
            evidence += wt0.evidence
            if not wt0.success:
                return SkillResult(success=False, error=wt0.error or "gui.wait failed", evidence=evidence)

            hk_sel = tool_call(context, "gui.hotkey", {"keys": ["ctrl", "a"]})
            evidence += hk_sel.evidence
            if not hk_sel.success:
                return SkillResult(success=False, error=hk_sel.error or "gui.hotkey ctrl+a failed", evidence=evidence)

            tt = tool_call(context, "gui.type_text", {"text": keyword})
            evidence += tt.evidence
            if not tt.success:
                return SkillResult(success=False, error=tt.error or "gui.type_text failed", evidence=evidence)

            wt_after_type = tool_call(context, "gui.wait", {"seconds": 0.1})
            evidence += wt_after_type.evidence
            if not wt_after_type.success:
                return SkillResult(success=False, error=wt_after_type.error or "gui.wait failed", evidence=evidence)

            hk2 = tool_call(context, "gui.hotkey", {"keys": ["enter"]})
            evidence += hk2.evidence
            if not hk2.success:
                return SkillResult(success=False, error=hk2.error or "gui.hotkey enter failed", evidence=evidence)

            wt = tool_call(context, "gui.wait", {"seconds": 0.5})
            evidence += wt.evidence
            if not wt.success:
                return SkillResult(success=False, error=wt.error or "gui.wait failed", evidence=evidence)

            return SkillResult(success=True, data={"keyword": keyword}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class DocsNewDocumentSkill(BaseSkill):
    name = "docs.new_document"
    description = "Create a new document in Docs."
    side_effect = True
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        evidence: list[str] = []
        try:
            keys = config_get(context, "docs.new_doc_hotkey", ["ctrl", "n"])
            if not isinstance(keys, list) or not keys:
                keys = ["ctrl", "n"]
            hk = tool_call(context, "gui.hotkey", {"keys": [str(k) for k in keys]})
            evidence += hk.evidence
            if not hk.success:
                return SkillResult(success=False, error=hk.error or "gui.hotkey failed", evidence=evidence)
            wt = tool_call(context, "gui.wait", {"seconds": 0.5})
            evidence += wt.evidence
            return SkillResult(success=wt.success, error=wt.error, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class InputTitleSkill(BaseSkill):
    name = "docs.input_title"
    description = "Type the document title."
    side_effect = True
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"title": {"type": "string"}},
        "required": ["title"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        title = str(params.get("title") or "")
        if not title:
            return SkillResult(success=False, error="title is required")
        evidence: list[str] = []
        try:
            tt = tool_call(context, "gui.type_text", {"text": title})
            evidence += tt.evidence
            if not tt.success:
                return SkillResult(success=False, error=tt.error or "gui.type_text failed", evidence=evidence)
            wt_after_type = tool_call(context, "gui.wait", {"seconds": 0.1})
            evidence += wt_after_type.evidence
            if not wt_after_type.success:
                return SkillResult(success=False, error=wt_after_type.error or "gui.wait failed", evidence=evidence)
            hk = tool_call(context, "gui.hotkey", {"keys": ["enter"]})
            evidence += hk.evidence
            if not hk.success:
                return SkillResult(success=False, error=hk.error or "gui.hotkey enter failed", evidence=evidence)
            return SkillResult(success=True, data={"title_len": len(title)}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class InputBodySkill(BaseSkill):
    name = "docs.input_body"
    description = "Type document body."
    side_effect = True
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"body": {"type": "string"}},
        "required": ["body"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        body = str(params.get("body") or "")
        if not body:
            return SkillResult(success=False, error="body is required")
        evidence: list[str] = []
        try:
            tt = tool_call(context, "gui.type_text", {"text": body})
            evidence += tt.evidence
            if not tt.success:
                return SkillResult(success=False, error=tt.error or "gui.type_text failed", evidence=evidence)
            return SkillResult(success=True, data={"body_len": len(body)}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class VerifyDocumentSkill(BaseSkill):
    name = "docs.verify_document"
    description = "Verify expected texts are visible in the document (OCR)."
    side_effect = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"texts": {"type": "array", "items": {"type": "string"}}},
        "required": ["texts"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        texts = params.get("texts")
        if not isinstance(texts, list) or not texts:
            return SkillResult(success=False, error="texts must be a non-empty list")
        evidence: list[str] = []
        try:
            app_res = OpenOrFocusSkill().execute({}, context)
            evidence += app_res.evidence
            if not app_res.success:
                return SkillResult(success=False, error=app_res.error or "app.open_or_focus failed", evidence=evidence)

            keywords = config_get(context, "app.feishu_window_title_keywords", None)
            title_keywords = [str(k) for k in keywords] if isinstance(keywords, list) and keywords else None
            filename = f"docs_verify_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
            shot_params: dict[str, Any] = {"filename": filename}
            if title_keywords:
                shot_params.update({"title_keywords": title_keywords, "crop_to_window": True})
            shot = tool_call(context, "screen.screenshot", shot_params)
            evidence += shot.evidence
            if not shot.success:
                return SkillResult(success=False, error=shot.error or "screen.screenshot failed", evidence=evidence)
            path = shot.data.get("path")
            if not path:
                return SkillResult(success=False, error="screen.screenshot did not return path", evidence=evidence)

            for t in [str(x) for x in texts]:
                ver = tool_call(context, "verify.text_visible", {"path": path, "text": t})
                evidence += ver.evidence
                if not ver.success:
                    return SkillResult(success=False, error=ver.error or f"text not visible: {t}", evidence=evidence)

            return SkillResult(success=True, data={"path": path, "texts": [str(x) for x in texts]}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class CreateDocumentSkill(BaseSkill):
    name = "docs.create_document"
    description = "Open docs, create document, input title/body, and verify."
    side_effect = True
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"doc_name": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}},
        "required": ["doc_name", "title", "body"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        doc_name = str(params.get("doc_name") or "")
        title = str(params.get("title") or "")
        body = str(params.get("body") or "")
        if not doc_name or not title or not body:
            return SkillResult(success=False, error="doc_name/title/body are required")

        evidence: list[str] = []
        try:
            s1 = OpenDocsHomeSkill().execute({}, context)
            evidence += s1.evidence
            if not s1.success:
                return SkillResult(success=False, error=s1.error or "docs.open_home failed", evidence=evidence)

            s2 = DocsNewDocumentSkill().execute({}, context)
            evidence += s2.evidence
            if not s2.success:
                return SkillResult(success=False, error=s2.error or "docs.new_document failed", evidence=evidence)

            # doc_name is used as part of verification text for now.
            s3 = InputTitleSkill().execute({"title": title}, context)
            evidence += s3.evidence
            if not s3.success:
                return SkillResult(success=False, error=s3.error or "docs.input_title failed", evidence=evidence)

            s4 = InputBodySkill().execute({"body": body}, context)
            evidence += s4.evidence
            if not s4.success:
                return SkillResult(success=False, error=s4.error or "docs.input_body failed", evidence=evidence)

            s5 = VerifyDocumentSkill().execute({"texts": [doc_name, title]}, context)
            evidence += s5.evidence
            if not s5.success:
                return SkillResult(success=False, error=s5.error or "docs.verify_document failed", evidence=evidence)

            return SkillResult(success=True, data={"doc_name": doc_name, "title": title}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


__all__ = [
    "OpenDocsHomeSkill",
    "DocsNewDocumentSkill",
    "InputTitleSkill",
    "InputBodySkill",
    "VerifyDocumentSkill",
    "CreateDocumentSkill",
]
