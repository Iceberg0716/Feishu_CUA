from __future__ import annotations

from typing import Any

from runtime.context import RunContext
from skills._helpers import config_get, tool_call
from skills.base import BaseSkill, SkillResult


class OpenOrFocusSkill(BaseSkill):
    name = "app.open_or_focus"
    description = "Open or focus Feishu/Lark desktop window."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"title_keywords": {"type": "array", "items": {"type": "string"}}},
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        try:
            keywords = params.get("title_keywords")
            if keywords is None:
                keywords = config_get(context, "app.feishu_window_title_keywords", None)
            if not isinstance(keywords, list) or not keywords:
                return SkillResult(success=False, error="title_keywords not provided and not found in config")

            res = tool_call(context, "gui.focus_window", {"title_keywords": [str(k) for k in keywords]})
            if not res.success:
                return SkillResult(success=False, error=res.error or "gui.focus_window failed", evidence=res.evidence)
            return SkillResult(success=True, data={"title": res.data.get("title")}, evidence=res.evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))


__all__ = ["OpenOrFocusSkill"]

