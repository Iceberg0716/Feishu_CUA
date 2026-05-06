from __future__ import annotations

from datetime import datetime
from typing import Any

from runtime.context import RunContext
from skills._helpers import config_get, tool_call
from skills.app import OpenOrFocusSkill
from skills.base import BaseSkill, SkillResult


class SearchChatSkill(BaseSkill):
    name = "im.search_chat"
    description = "Search and open a chat by name in IM."
    side_effect = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"chat_name": {"type": "string"}},
        "required": ["chat_name"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        chat_name = str(params.get("chat_name") or "")
        if not chat_name:
            return SkillResult(success=False, error="chat_name is required")

        evidence: list[str] = []
        try:
            hk1 = tool_call(context, "gui.hotkey", {"keys": ["ctrl", "k"]})
            evidence += hk1.evidence
            if not hk1.success:
                return SkillResult(success=False, error=hk1.error or "gui.hotkey failed", evidence=evidence)

            # Give Feishu a moment to focus the global search input.
            wt0 = tool_call(context, "gui.wait", {"seconds": 0.1})
            evidence += wt0.evidence
            if not wt0.success:
                return SkillResult(success=False, error=wt0.error or "gui.wait failed", evidence=evidence)

            # Ensure we replace any previous query.
            hk_sel = tool_call(context, "gui.hotkey", {"keys": ["ctrl", "a"]})
            evidence += hk_sel.evidence
            if not hk_sel.success:
                return SkillResult(success=False, error=hk_sel.error or "gui.hotkey ctrl+a failed", evidence=evidence)

            tt = tool_call(context, "gui.type_text", {"text": chat_name})
            evidence += tt.evidence
            if not tt.success:
                return SkillResult(success=False, error=tt.error or "gui.type_text failed", evidence=evidence)

            # Some clients need a tiny delay to apply clipboard paste before we move on.
            after_paste_wait = float(config_get(context, "im.after_paste_chat_name_wait_seconds", 0.1))
            if after_paste_wait > 0:
                wt_paste = tool_call(context, "gui.wait", {"seconds": after_paste_wait})
                evidence += wt_paste.evidence
                if not wt_paste.success:
                    return SkillResult(success=False, error=wt_paste.error or "gui.wait failed", evidence=evidence)

            # Give the UI time to populate search results before pressing Enter.
            after_type_wait = float(config_get(context, "im.search_results_wait_seconds", 0.4))
            wt_after_type = tool_call(context, "gui.wait", {"seconds": after_type_wait})
            evidence += wt_after_type.evidence
            if not wt_after_type.success:
                return SkillResult(success=False, error=wt_after_type.error or "gui.wait failed", evidence=evidence)

            # Operation path default: Ctrl+K -> Ctrl+A -> paste chat_name -> Enter (no Down).
            # If Enter-only doesn't open the chat reliably on your setup, set `im.search_select_first_result: down_enter`.
            select_first = str(config_get(context, "im.search_select_first_result", "enter")).strip().lower()
            if select_first == "down_enter":
                hk_down = tool_call(context, "gui.hotkey", {"keys": ["down"]})
                evidence += hk_down.evidence
                if not hk_down.success:
                    return SkillResult(success=False, error=hk_down.error or "gui.hotkey down failed", evidence=evidence)
                wt_down = tool_call(context, "gui.wait", {"seconds": 0.05})
                evidence += wt_down.evidence
                if not wt_down.success:
                    return SkillResult(success=False, error=wt_down.error or "gui.wait failed", evidence=evidence)

            enter_times = int(config_get(context, "im.open_chat_enter_times", 1) or 1)
            enter_times = max(1, min(3, enter_times))
            for n in range(enter_times):
                hk2 = tool_call(context, "gui.hotkey", {"keys": ["enter"]})
                evidence += hk2.evidence
                if not hk2.success:
                    return SkillResult(success=False, error=hk2.error or "gui.hotkey enter failed", evidence=evidence)
                if n < enter_times - 1:
                    wt_enter = tool_call(context, "gui.wait", {"seconds": 0.05})
                    evidence += wt_enter.evidence
                    if not wt_enter.success:
                        return SkillResult(success=False, error=wt_enter.error or "gui.wait failed", evidence=evidence)

            # Wait for the search result to open the chat view.
            open_wait = float(config_get(context, "im.open_chat_wait_seconds", 0.6))
            wt1 = tool_call(context, "gui.wait", {"seconds": open_wait})
            evidence += wt1.evidence
            if not wt1.success:
                return SkillResult(success=False, error=wt1.error or "gui.wait failed", evidence=evidence)

            if bool(config_get(context, "im.close_search_overlay_after_open", False)):
                hk_close = tool_call(context, "gui.hotkey", {"keys": ["esc"]})
                evidence += hk_close.evidence
                if not hk_close.success:
                    return SkillResult(success=False, error=hk_close.error or "gui.hotkey esc failed", evidence=evidence)

                wt2 = tool_call(context, "gui.wait", {"seconds": 0.05})
                evidence += wt2.evidence
                if not wt2.success:
                    return SkillResult(success=False, error=wt2.error or "gui.wait failed", evidence=evidence)

            return SkillResult(success=True, data={"chat_name": chat_name}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class SendTextSkill(BaseSkill):
    name = "im.send_text"
    description = "Send a text message in current chat."
    side_effect = True
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        message = str(params.get("message") or "")
        if not message:
            return SkillResult(success=False, error="message is required")

        evidence: list[str] = []
        try:
            if bool(config_get(context, "im.click_message_input_before_typing", False)):
                keywords = config_get(context, "app.feishu_window_title_keywords", None)
                title_keywords = [str(k) for k in keywords] if isinstance(keywords, list) and keywords else ["Feishu", "Lark"]
                x_ratio = float(config_get(context, "im.message_input_x_ratio", 0.65))
                y_ratio = float(config_get(context, "im.message_input_y_ratio", 0.92))
                clk = tool_call(
                    context,
                    "gui.click_window_relative",
                    {"title_keywords": title_keywords, "x_ratio": x_ratio, "y_ratio": y_ratio},
                )
                evidence += clk.evidence
                if not clk.success:
                    return SkillResult(success=False, error=clk.error or "gui.click_window_relative failed", evidence=evidence)

                wt_focus = tool_call(context, "gui.wait", {"seconds": 0.05})
                evidence += wt_focus.evidence
                if not wt_focus.success:
                    return SkillResult(success=False, error=wt_focus.error or "gui.wait failed", evidence=evidence)

            tt = tool_call(context, "gui.type_text", {"text": message})
            evidence += tt.evidence
            if not tt.success:
                return SkillResult(success=False, error=tt.error or "gui.type_text failed", evidence=evidence)

            wt_after_type = tool_call(context, "gui.wait", {"seconds": 0.1})
            evidence += wt_after_type.evidence
            if not wt_after_type.success:
                return SkillResult(success=False, error=wt_after_type.error or "gui.wait failed", evidence=evidence)

            send_keys = config_get(context, "im.send_keys", ["enter"])
            if not isinstance(send_keys, list) or not send_keys:
                send_keys = ["enter"]
            hk = tool_call(context, "gui.hotkey", {"keys": [str(k) for k in send_keys]})
            evidence += hk.evidence
            if not hk.success:
                return SkillResult(success=False, error=hk.error or "gui.hotkey enter failed", evidence=evidence)

            return SkillResult(success=True, data={"message_len": len(message)}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class VerifyMessageSkill(BaseSkill):
    name = "im.verify_message"
    description = "Verify target message is visible in current chat."
    side_effect = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        text = str(params.get("text") or "")
        if not text:
            return SkillResult(success=False, error="text is required")

        evidence: list[str] = []
        try:
            app_res = OpenOrFocusSkill().execute({}, context)
            evidence += app_res.evidence
            if not app_res.success:
                return SkillResult(success=False, error=app_res.error or "app.open_or_focus failed", evidence=evidence)

            keywords = config_get(context, "app.feishu_window_title_keywords", None)
            title_keywords = [str(k) for k in keywords] if isinstance(keywords, list) and keywords else None
            filename = f"im_verify_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
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

            ver = tool_call(context, "verify.text_visible", {"path": path, "text": text})
            evidence += ver.evidence
            if not ver.success:
                return SkillResult(success=False, error=ver.error or "verify.text_visible failed", evidence=evidence)

            return SkillResult(success=True, data={"path": path, "text": text}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


class SendMessageSkill(BaseSkill):
    name = "im.send_message"
    description = "Open or focus app, search chat, send message, then verify it."
    side_effect = True
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"chat_name": {"type": "string"}, "message": {"type": "string"}},
        "required": ["chat_name", "message"],
    }

    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        chat_name = str(params.get("chat_name") or "")
        message = str(params.get("message") or "")
        if not chat_name or not message:
            return SkillResult(success=False, error="chat_name and message are required")

        evidence: list[str] = []
        try:
            s1 = OpenOrFocusSkill().execute({}, context)
            evidence += s1.evidence
            if not s1.success:
                return SkillResult(success=False, error=s1.error or "app.open_or_focus failed", evidence=evidence)

            s2 = SearchChatSkill().execute({"chat_name": chat_name}, context)
            evidence += s2.evidence
            if not s2.success:
                return SkillResult(success=False, error=s2.error or "im.search_chat failed", evidence=evidence)

            s3 = SendTextSkill().execute({"message": message}, context)
            evidence += s3.evidence
            if not s3.success:
                return SkillResult(success=False, error=s3.error or "im.send_text failed", evidence=evidence)

            s4 = VerifyMessageSkill().execute({"text": message}, context)
            evidence += s4.evidence
            if not s4.success:
                return SkillResult(success=False, error=s4.error or "im.verify_message failed", evidence=evidence)

            return SkillResult(success=True, data={"chat_name": chat_name, "message": message}, evidence=evidence)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc), evidence=evidence)


__all__ = [
    "SearchChatSkill",
    "SendTextSkill",
    "VerifyMessageSkill",
    "SendMessageSkill",
]
