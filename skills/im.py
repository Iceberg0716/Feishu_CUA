from __future__ import annotations

from datetime import datetime
from typing import Any

from runtime.context import RunContext
from skills._helpers import config_get, tool_call
from skills.app import OpenOrFocusSkill
from skills.base import BaseSkill, SkillResult
from tools.schema import ToolResult


def _bbox_to_int4(bbox: object) -> list[int] | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(float(v)) for v in bbox)
    except Exception:
        return None
    x1, x2 = (x1, x2) if x1 <= x2 else (x2, x1)
    y1, y2 = (y1, y2) if y1 <= y2 else (y2, y1)
    return [x1, y1, x2, y2]


def _click_point_from_bbox(bbox: list[int], *, w: int, h: int) -> list[int]:
    x1, y1, x2, y2 = bbox
    click_x = max(120, x1 - 80)
    click_x = max(1, min(w - 2, int(click_x)))
    click_y = max(1, min(h - 2, int((y1 + y2) / 2)))
    return [click_x, click_y]


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

        vision_ocr_enabled_raw = config_get(context, "vision.ocr_enabled", None)
        if vision_ocr_enabled_raw is None:
            ocr_enabled = bool(config_get(context, "ocr.enabled", True))
        else:
            ocr_enabled = bool(vision_ocr_enabled_raw)

        evidence: list[str] = []

        def _ev(tag: str) -> None:
            evidence.append(tag)

        def _verify_chat_opened() -> ToolResult:
            keywords = config_get(context, "app.feishu_window_title_keywords", None)
            title_keywords = [str(k) for k in keywords] if isinstance(keywords, list) and keywords else None
            if not title_keywords:
                return ToolResult(success=True, data={"skipped": True}, evidence=["verify_chat_opened:skipped:no_title_keywords"])

            try:
                shot = tool_call(
                    context,
                    "screen.screenshot",
                    {
                        "filename": f"search_verify_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png",
                        "title_keywords": title_keywords,
                        "crop_to_window": True,
                    },
                )
            except KeyError:
                return ToolResult(success=True, data={"skipped": True}, evidence=["verify_chat_opened:skipped:tool_missing:screen.screenshot"])
            out_ev = list(shot.evidence or [])
            if not shot.success:
                return ToolResult(success=False, error=shot.error or "screen.screenshot failed", evidence=out_ev)
            path = shot.data.get("path") if isinstance(shot.data, dict) else None
            if not path:
                return ToolResult(success=False, error="screen.screenshot did not return path", evidence=out_ev)

            expectation = (
                "You are a GUI QA assistant.\n"
                "Decide whether the screenshot shows an ACTIVE Feishu/Lark IM chat conversation view (message list + message input box),\n"
                f"and the current chat is named '{chat_name}'.\n"
                "It MUST NOT be the Ctrl+K search results page/overlay.\n"
                "Return ONLY strict JSON with keys: success(boolean), confidence(number 0-1), reason(string)."
            )
            try:
                judge = tool_call(context, "vlm.judge_state", {"path": path, "expectation": expectation, "timeout_seconds": 30})
            except KeyError:
                return ToolResult(success=False, error="vlm.judge_state tool missing", evidence=out_ev + ["verify_chat_opened:tool_missing:vlm.judge_state"])
            out_ev += list(judge.evidence or [])
            if judge.success:
                return ToolResult(success=True, data={"ok": True}, evidence=out_ev)
            reason = judge.data.get("reason") if isinstance(judge.data, dict) else None
            return ToolResult(success=False, error=reason or "verify_chat_opened failed", evidence=out_ev)

        if ocr_enabled:
            _ev("open_strategy:ocr_vlm_click")
        else:
            _ev("open_strategy:vlm_only")

        max_retries = int(config_get(context, "im.search_chat_max_retries", 2) or 2)
        max_retries = max(0, min(5, max_retries))
        max_attempts = max_retries + 1
        last_err: str | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                _ev(f"attempt:{attempt}/{max_attempts}")

                focus_res = OpenOrFocusSkill().execute({}, context)
                evidence += focus_res.evidence
                if not focus_res.success:
                    return SkillResult(success=False, error=focus_res.error or "app.open_or_focus failed", evidence=evidence)

                after_ctrl_k_wait = float(config_get(context, "im.after_ctrl_k_wait_seconds", 0.5) or 0.5)
                after_ctrl_a_wait = float(config_get(context, "im.after_ctrl_a_wait_seconds", 0.2) or 0.2)
                after_paste_wait = float(config_get(context, "im.after_paste_chat_name_wait_seconds", 1.0) or 1.0)
                search_results_wait = float(config_get(context, "im.search_results_wait_seconds", 1.0) or 1.0)
                after_open_chat_wait = float(config_get(context, "im.after_open_chat_wait_seconds", 1.0) or 1.0)
                ocr_min_conf = float(config_get(context, "im.ocr_candidate_min_confidence", 0.5) or 0.5)
                search_box_ratio = float(config_get(context, "im.search_box_region_max_y_ratio", 0.12) or 0.12)
                search_box_ratio = max(0.05, min(0.25, search_box_ratio))

                _ev("before:ctrl+k")
                hk1 = tool_call(context, "gui.hotkey", {"keys": ["ctrl", "k"]})
                evidence += list(hk1.evidence or [])
                if not hk1.success:
                    return SkillResult(success=False, error=hk1.error or "gui.hotkey ctrl+k failed", evidence=evidence)
                _ev("after:ctrl+k")

                wt0 = tool_call(context, "gui.wait", {"seconds": after_ctrl_k_wait})
                evidence += list(wt0.evidence or [])
                if not wt0.success:
                    return SkillResult(success=False, error=wt0.error or "gui.wait failed", evidence=evidence)

                _ev("before:ctrl+a")
                hk_sel = tool_call(context, "gui.hotkey", {"keys": ["ctrl", "a"]})
                evidence += list(hk_sel.evidence or [])
                if not hk_sel.success:
                    return SkillResult(success=False, error=hk_sel.error or "gui.hotkey ctrl+a failed", evidence=evidence)
                _ev("after:ctrl+a")

                wt1 = tool_call(context, "gui.wait", {"seconds": after_ctrl_a_wait})
                evidence += list(wt1.evidence or [])
                if not wt1.success:
                    return SkillResult(success=False, error=wt1.error or "gui.wait failed", evidence=evidence)

                _ev("before:paste_chat_name")
                tt = tool_call(context, "gui.type_text", {"text": chat_name})
                evidence += list(tt.evidence or [])
                if not tt.success:
                    return SkillResult(success=False, error=tt.error or "gui.type_text failed", evidence=evidence)
                _ev("after:paste_chat_name")

                wt_paste = tool_call(context, "gui.wait", {"seconds": after_paste_wait})
                evidence += list(wt_paste.evidence or [])
                if not wt_paste.success:
                    return SkillResult(success=False, error=wt_paste.error or "gui.wait failed", evidence=evidence)

                keywords = config_get(context, "app.feishu_window_title_keywords", None)
                title_keywords = [str(k) for k in keywords] if isinstance(keywords, list) and keywords else None
                if not title_keywords:
                    return SkillResult(success=False, error="app.feishu_window_title_keywords is required for OCR/VLM click strategy", evidence=evidence)

                wt_search = tool_call(context, "gui.wait", {"seconds": search_results_wait})
                evidence += list(wt_search.evidence or [])
                if not wt_search.success:
                    return SkillResult(success=False, error=wt_search.error or "gui.wait failed", evidence=evidence)

                try:
                    shot = tool_call(
                        context,
                        "screen.screenshot",
                        {
                            "filename": f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png",
                            "title_keywords": title_keywords,
                            "crop_to_window": True,
                        },
                    )
                except KeyError:
                    return SkillResult(success=False, error="screen.screenshot tool missing", evidence=evidence)
                evidence += list(shot.evidence or [])
                if not shot.success:
                    return SkillResult(success=False, error=shot.error or "screen.screenshot failed", evidence=evidence)
                path = shot.data.get("path") if isinstance(shot.data, dict) else None
                if not path:
                    return SkillResult(success=False, error="screen.screenshot did not return path", evidence=evidence)
                _ev(f"screenshot:search_results:{path}")

                crop_left = 0
                crop_top = 0
                crop_w = 0
                crop_h = 0
                for ev in list(shot.evidence or []):
                    if isinstance(ev, str) and ev.startswith("screenshot_crop:"):
                        try:
                            _, payload = ev.split(":", 1)
                            parts = [int(float(x)) for x in payload.split(",")]
                            if len(parts) >= 4:
                                crop_left, crop_top, crop_w, crop_h = parts[0], parts[1], parts[2], parts[3]
                        except Exception:
                            pass
                if crop_w <= 0 or crop_h <= 0:
                    return SkillResult(success=False, error="screenshot_crop missing; crop_to_window must be enabled", evidence=evidence)

                selected_source = "none"
                selected_reason = ""
                selected_bbox: list[int] | None = None
                click_rel: list[int] | None = None

                if ocr_enabled:
                    try:
                        loc = tool_call(
                            context,
                            "vision.locate_text",
                            {"path": path, "text": chat_name, "mode": "contains", "case_sensitive": False, "min_confidence": ocr_min_conf},
                        )
                    except KeyError:
                        return SkillResult(success=False, error="vision.locate_text tool missing", evidence=evidence)
                    evidence += list(loc.evidence or [])
                    matches = loc.data.get("matches") if isinstance(loc.data, dict) else None
                    if not isinstance(matches, list):
                        matches = []
                    _ev(f"ocr_candidate_count:{len(matches)}")
                    for m in matches:
                        if not isinstance(m, dict):
                            continue
                        bbox = _bbox_to_int4(m.get("bbox"))
                        if bbox is None:
                            continue
                        selected_source = "ocr"
                        selected_reason = "locate_text:first_match"
                        selected_bbox = bbox
                        click_rel = _click_point_from_bbox(bbox, w=crop_w, h=crop_h)
                        break

                if selected_source != "ocr":
                    try:
                        vlm = tool_call(
                            context,
                            "vlm.find_chat_candidate",
                            {"path": path, "chat_name": chat_name, "search_box_max_y": int(crop_h * search_box_ratio), "timeout_seconds": 30},
                        )
                    except KeyError:
                        vlm = ToolResult(success=False, error="vlm.find_chat_candidate tool missing")
                    evidence += list(vlm.evidence or [])
                    if vlm.success and isinstance(vlm.data, dict):
                        selected_source = "vlm"
                        selected_reason = str(vlm.data.get("reason") or "")
                        selected_bbox = _bbox_to_int4(vlm.data.get("bbox"))
                        cp = vlm.data.get("click_point")
                        if isinstance(cp, (list, tuple)) and len(cp) == 2:
                            try:
                                click_rel = [int(float(cp[0])), int(float(cp[1]))]
                            except Exception:
                                click_rel = None
                    else:
                        selected_source = "none"
                        selected_reason = vlm.error or "no reliable ocr candidate and vlm failed"

                _ev(f"selected_candidate_source:{selected_source}")
                _ev(f"selected_candidate_reason:{selected_reason}")
                if selected_bbox is not None:
                    _ev(f"selected_candidate_bbox:{','.join(str(v) for v in selected_bbox)}")

                if click_rel is None:
                    last_err = f"no reliable chat candidate for '{chat_name}'"
                    if attempt < max_attempts:
                        continue
                    return SkillResult(success=False, error=last_err, evidence=evidence)

                click_x_rel, click_y_rel = int(click_rel[0]), int(click_rel[1])
                if not (0 <= click_x_rel < crop_w and 0 <= click_y_rel < crop_h):
                    last_err = "selected click_point out of screenshot bounds"
                    if attempt < max_attempts:
                        continue
                    return SkillResult(success=False, error=last_err, evidence=evidence)
                if click_y_rel < int(crop_h * search_box_ratio):
                    last_err = "selected click_point is inside search box region"
                    if attempt < max_attempts:
                        continue
                    return SkillResult(success=False, error=last_err, evidence=evidence)

                click_x = max(0, int(crop_left) + click_x_rel)
                click_y = max(0, int(crop_top) + click_y_rel)
                _ev(f"click:{click_x},{click_y}")
                clk = tool_call(context, "gui.click", {"x": click_x, "y": click_y})
                evidence += list(clk.evidence or [])
                if not clk.success:
                    return SkillResult(success=False, error=clk.error or "gui.click failed", evidence=evidence)

                wt_open = tool_call(context, "gui.wait", {"seconds": after_open_chat_wait})
                evidence += list(wt_open.evidence or [])
                if not wt_open.success:
                    return SkillResult(success=False, error=wt_open.error or "gui.wait failed", evidence=evidence)

                ver = _verify_chat_opened()
                evidence += list(ver.evidence or [])
                if ver.success:
                    _ev("verify_chat_opened:true")
                    return SkillResult(success=True, data={"chat_name": chat_name}, evidence=evidence)

                last_err = ver.error or "verify_chat_opened failed"
                _ev("verify_chat_opened:false")
                if attempt < max_attempts:
                    continue

                return SkillResult(success=False, error=last_err, evidence=evidence)
            except Exception as exc:
                last_err = str(exc)
                _ev(f"exception:{last_err}")
                if attempt < max_attempts:
                    continue
                return SkillResult(success=False, error=last_err, evidence=evidence)

        # Defensive fallback (should not be reachable).
        return SkillResult(success=False, error=last_err or "search_chat failed", evidence=evidence)


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
