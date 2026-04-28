"""Main agent loop: screenshot → VLM analyze → parse → execute → verify → record."""

import time
from dataclasses import dataclass

from PIL import Image

from .config import config
from .execution.action_types import (
    Action,
    ClickAction,
    DoubleClickAction,
)
from .execution.operator import execute
from .execution.parser import parse_action
from .perception.screenshot import Screenshot
from .perception.vlm_client import analyze_screen
from .recorder import Recorder
from .verification.verifier import verify as verify_step


VLM_MAX_WIDTH = 1280  # screens wider than this get scaled down for VLM


def _calc_vlm_size(native_width: int) -> int:
    """Auto-decide VLM input width based on native screen resolution.

    Rule: screens > 1920px wide (2K/4K/high-DPI) are scaled to 1280px.
    Screens <= 1920px (standard 1080p) are used as-is.
    """
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
    """Scale coordinate-based actions back to native resolution."""
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


class Orchestrator:
    def __init__(self):
        self.screenshot = Screenshot()
        self.recorder = Recorder()

    def run_step(self, instruction: str) -> StepResult:
        t0 = time.time()

        # 1. Capture BEFORE screenshot
        before_img, before_path = self.screenshot.capture()

        # 2. Auto-decide VLM input width and resize if needed
        vlm_target = _calc_vlm_size(before_img.width)
        vlm_img, scale = _resize_for_vlm(before_img, vlm_target)

        # 3. Ask VLM to analyze screen and plan the action
        vlm_resp = analyze_screen(vlm_img, instruction)

        # 4. Parse VLM response, scale coordinates back to native resolution
        vlm_w, vlm_h = vlm_img.size
        action = parse_action(vlm_resp.raw_response, vlm_w, vlm_h)
        native_action = _scale_action_coords(action, 1.0 / scale)
        print(f"[VLM] thought: {vlm_resp.thought}")
        print(f"[VLM] action: {vlm_resp.action} params={vlm_resp.params} conf={vlm_resp.confidence}")
        if scale != 1.0:
            print(f"[SCALE] native {before_img.width}px -> vlm {vlm_w}px, coord factor {1.0/scale:.2f}")
        action = native_action

        # 5. Execute the action
        execute(action)
        time.sleep(0.5)  # wait for UI to settle

        # 6. Capture AFTER screenshot, resize with same target width
        after_img, after_path = self.screenshot.capture()
        vlm_after_img, _ = _resize_for_vlm(after_img, vlm_target)

        # 7. Verify result (use resized images for VLM)
        verdict = verify_step(vlm_img, vlm_after_img, instruction)

        # 8. Record trace
        self.recorder.record(
            instruction=instruction,
            vlm_raw=vlm_resp.raw_response,
            action=action,
            verdict_passed=verdict.passed,
            verdict_reason=verdict.reason,
            before_path=before_path,
            after_path=after_path,
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
        )
