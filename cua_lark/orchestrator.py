"""Main agent loop: screenshot → VLM analyze → parse → execute → verify → record."""

import time
from dataclasses import dataclass

from .config import config
from .execution.action_types import Action
from .execution.operator import execute
from .execution.parser import parse_action
from .perception.screenshot import Screenshot
from .perception.vlm_client import analyze_screen
from .recorder import Recorder
from .verification.verifier import verify as verify_step


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

        # 2. Ask VLM to analyze screen and plan the action
        scr_w, scr_h = self.screenshot.screen_size
        vlm_resp = analyze_screen(before_img, instruction)

        # 3. Parse VLM response into Action object
        action = parse_action(vlm_resp.raw_response, scr_w, scr_h)

        # 4. Execute the action
        execute(action)
        time.sleep(0.5)  # wait for UI to settle

        # 5. Capture AFTER screenshot
        after_img, after_path = self.screenshot.capture()

        # 6. Verify result
        verdict = verify_step(before_img, after_img, instruction)

        # 7. Record trace
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
