"""Main agent loop: screenshot -> VLM analyze -> parse -> execute -> verify -> record."""

import time
from dataclasses import dataclass

from PIL import Image

from .config import config
from .execution.recovery import ensure_target_app_focused, recover_to_known_state
from .execution.input_guard import wait_for_user_idle
from .execution.action_types import (
    Action,
    ClickAction,
    DoubleClickAction,
)
from .execution.operator import execute
from .execution.parser import parse_action
from .knowledge_base import load_app_knowledge
from .perception.state_classifier import classify_state
from .perception.screenshot import Screenshot
from .perception.vlm_client import analyze_screen
from .recorder import Recorder
from .verification.verifier import verify as verify_step


VLM_MAX_WIDTH = 1280


def _calc_vlm_size(native_width: int) -> int:
    if native_width > 1920:
        return VLM_MAX_WIDTH
    return native_width


def _resize_for_vlm(img: Image.Image, target_width: int) -> tuple[Image.Image, float]:
    w, h = img.size
    if w <= target_width:
        return img, 1.0
    scale = target_width / w
    new_h = int(h * scale)
    return img.resize((target_width, new_h), Image.LANCZOS), scale


def _scale_action_coords(action: Action, factor: float) -> Action:
    if factor == 1.0:
        return action
    if isinstance(action, (ClickAction, DoubleClickAction)):
        action.x = round(action.x * factor)
        action.y = round(action.y * factor)
    return action


@dataclass
class StepResult:
    instruction: str
    action: Action | None
    verdict_passed: bool
    verdict_reason: str
    before_path: str
    after_path: str
    vlm_raw: str
    elapsed_ms: float
    page_state: str
    recovery_reason: str
    attempts: int


class Orchestrator:
    def __init__(self):
        self.knowledge = load_app_knowledge(config.app_knowledge_path)
        self.screenshot = Screenshot(
            output_dir=config.screenshot_dir,
            prefix=config.screenshot_prefix,
        )
        self.recorder = Recorder()

    def _run_step_once(self, instruction: str) -> StepResult:
        t0 = time.time()
        recovery_reason = ""

        wait_for_user_idle(
            idle_timeout_s=config.input_idle_timeout_s,
            poll_interval_s=config.input_poll_interval_s,
        )

        focus_result = ensure_target_app_focused(self.knowledge)
        if not focus_result.recovered:
            raise RuntimeError(f"无法聚焦目标应用: {focus_result.reason}")

        before_img, before_path = self.screenshot.capture("before", instruction=instruction)
        page_state = classify_state(before_img, self.knowledge)
        print(
            f"[STATE] app_in_view={page_state.app_in_view} state={page_state.state} "
            f"conf={page_state.confidence} reason={page_state.reason}"
        )
        if not page_state.app_in_view or page_state.state == "unknown":
            recovery = recover_to_known_state(
                "初始页面未知或目标应用不在视图中",
                self.knowledge,
                current_state=page_state.state,
            )
            recovery_reason = recovery.reason
            if not recovery.recovered:
                raise RuntimeError(f"恢复失败: {recovery.reason}")
            wait_for_user_idle(
                idle_timeout_s=config.input_idle_timeout_s,
                poll_interval_s=config.input_poll_interval_s,
            )
            before_img, before_path = self.screenshot.capture("before_recovered", instruction=instruction)
            page_state = classify_state(before_img, self.knowledge)
            print(
                f"[STATE-RECOVERED] app_in_view={page_state.app_in_view} state={page_state.state} "
                f"conf={page_state.confidence} reason={page_state.reason}"
            )

        vlm_target = _calc_vlm_size(before_img.width)
        vlm_img, scale = _resize_for_vlm(before_img, vlm_target)

        vlm_resp = analyze_screen(vlm_img, instruction)

        vlm_w, vlm_h = vlm_img.size
        action = parse_action(vlm_resp.raw_response, vlm_w, vlm_h)
        native_action = _scale_action_coords(action, 1.0 / scale)
        print(f"[VLM] thought: {vlm_resp.thought}")
        print(f"[VLM] action: {vlm_resp.action} params={vlm_resp.params} conf={vlm_resp.confidence}")
        if scale != 1.0:
            print(f"[SCALE] native {before_img.width}px -> vlm {vlm_w}px, coord factor {1.0/scale:.2f}")
        action = native_action

        execute(action)
        wait_for_user_idle(
            idle_timeout_s=min(config.input_idle_timeout_s, config.post_action_settle_timeout_s),
            poll_interval_s=config.post_action_settle_poll_s,
        )

        after_img, after_path = self.screenshot.capture("after", instruction=instruction)
        vlm_after_img, _ = _resize_for_vlm(after_img, vlm_target)

        verdict = verify_step(vlm_img, vlm_after_img, instruction)
        if not verdict.passed:
            recovery = recover_to_known_state(
                f"验证失败: {verdict.reason}",
                self.knowledge,
                current_state=page_state.state,
            )
            if recovery.recovered:
                recovery_reason = recovery.reason
            else:
                recovery_reason = f"{recovery_reason}; {recovery.reason}".strip("; ")

        self.recorder.record(
            instruction=instruction,
            vlm_raw=vlm_resp.raw_response,
            action=action,
            verdict_passed=verdict.passed,
            verdict_reason=verdict.reason,
            before_path=before_path,
            after_path=after_path,
        )

        keep_screenshots = (
            (verdict.passed and config.screenshot_keep_passed)
            or ((not verdict.passed) and config.screenshot_keep_failed)
        )
        self.screenshot.mark_step(
            before_path=before_path,
            after_path=after_path,
            keep=keep_screenshots,
            verdict="PASS" if verdict.passed else "FAIL",
        )
        self.screenshot.cleanup_sessions(
            keep_latest=config.screenshot_keep_latest_sessions,
            max_age_hours=config.screenshot_keep_max_age_hours,
        )

        elapsed = (time.time() - t0) * 1000
        return StepResult(
            instruction=instruction,
            action=action,
            verdict_passed=verdict.passed,
            verdict_reason=verdict.reason,
            before_path=before_path,
            after_path=after_path,
            vlm_raw=vlm_resp.raw_response,
            elapsed_ms=elapsed,
            page_state=page_state.state,
            recovery_reason=recovery_reason,
            attempts=1,
        )

    def run_step(self, instruction: str) -> StepResult:
        last_result: StepResult | None = None
        last_error: Exception | None = None

        for attempt in range(1, config.recovery_max_attempts + 1):
            try:
                result = self._run_step_once(instruction)
                result.attempts = attempt
                last_result = result
                if result.verdict_passed:
                    return result
                if attempt < config.recovery_max_attempts:
                    print(
                        f"[RETRY] attempt={attempt} verdict=FAIL "
                        f"recovery={result.recovery_reason or 'none'}"
                    )
                    continue
                return result
            except Exception as exc:
                last_error = exc
                if attempt < config.recovery_max_attempts:
                    recovery = recover_to_known_state(
                        f"异常重试前恢复: {exc}",
                        self.knowledge,
                        current_state="unknown",
                    )
                    print(
                        f"[RETRY-ERROR] attempt={attempt} error={exc} "
                        f"recovery={recovery.reason}"
                    )
                    continue
                raise

        if last_error is not None:
            raise last_error
        if last_result is not None:
            return last_result
        raise RuntimeError("未能执行任务")
