"""Agent orchestrator: multi-step planning + self-healing execution loop."""

import time
from dataclasses import dataclass, field

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
from .perception.vlm_client import (
    analyze_screen,
    call_vlm_for_heal,
)
from .planning.planner import PlanStep, TaskPlan, create_plan
from .recorder import Recorder
from .verification.verifier import verify as verify_step

VLM_MAX_WIDTH = 1280
MAX_HEAL_RETRIES = 2


# ── image scaling ──────────────────────────────────────────────

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


# ── result types ──────────────────────────────────────────────

@dataclass
class StepResult:
    step_index: int
    instruction: str
    action: Action | None
    verdict_passed: bool
    verdict_reason: str
    before_path: str
    after_path: str
    vlm_raw: str
    elapsed_ms: float
    heal_attempts: int = 0
    heal_reason: str = ""


@dataclass
class TaskResult:
    instruction: str
    passed: bool
    total_steps: int
    passed_steps: int
    steps: list[StepResult] = field(default_factory=list)
    total_elapsed_ms: float = 0


# ── orchestrator ──────────────────────────────────────────────

class Orchestrator:
    def __init__(self):
        self.screenshot = Screenshot()
        self.recorder = Recorder()

    # ── single-step (kept for backward compat) ─────────────────

    def run_step(self, instruction: str) -> StepResult:
        return self._execute_one_step(instruction, step_index=0)

    # ── multi-step with self-healing ───────────────────────────

    def run_task(self, instruction: str) -> TaskResult:
        t0 = time.time()

        # 1. Take initial screenshot for planning
        before_img, before_path = self.screenshot.capture()
        vlm_target = _calc_vlm_size(before_img.width)
        vlm_img, scale = _resize_for_vlm(before_img, vlm_target)

        # 2. Plan: VLM breaks instruction into ordered steps
        plan = create_plan(vlm_img, instruction)
        print(f"[PLAN] {instruction}")
        for s in plan.steps:
            print(f"  Step {s.index}: {s.description} → expect: {s.expected}")

        # 3. Execute each step with self-healing
        task = TaskResult(
            instruction=instruction,
            passed=True,
            total_steps=len(plan.steps),
            passed_steps=0,
        )

        for step in plan.steps:
            result = self._execute_with_heal(step)
            task.steps.append(result)

            if result.verdict_passed:
                task.passed_steps += 1
            else:
                task.passed = False
                print(f"[ABORT] Step {step.index} failed after {result.heal_attempts} heal attempts, stopping task.")
                break

        task.total_elapsed_ms = (time.time() - t0) * 1000
        return task

    # ── internal: execute one step with self-healing ───────────

    def _execute_with_heal(self, step: PlanStep) -> StepResult:
        """Execute a plan step. On failure, ask VLM for alternatives (up to MAX_HEAL_RETRIES)."""
        for heal_round in range(MAX_HEAL_RETRIES + 1):
            if heal_round > 0:
                print(f"[HEAL] attempt {heal_round}/{MAX_HEAL_RETRIES} for step {step.index}")

            result = self._execute_one_step(step.description, step.index)

            if result.verdict_passed:
                return result

            # Self-heal: ask VLM what went wrong and what to try instead
            if heal_round < MAX_HEAL_RETRIES:
                alt = self._generate_heal(step, result)
                if alt:
                    step.description = alt
                    result.heal_attempts = heal_round + 1

        return result

    def _generate_heal(self, step: PlanStep, failed: StepResult) -> str | None:
        """Ask VLM to analyze failure and suggest an alternative instruction."""
        try:
            # Use the after-failure screenshot for analysis
            after_img, _ = self.screenshot.capture()
            vlm_target = _calc_vlm_size(after_img.width)
            vml_img, scale = _resize_for_vlm(after_img, vlm_target)

            reason, alternative = call_vlm_for_heal(
                vml_img, step.description, failed.verdict_reason
            )
            print(f"[HEAL] reason: {reason}")
            print(f"[HEAL] alternative: {alternative}")
            return alternative if alternative else None
        except Exception as e:
            print(f"[HEAL] VLM analysis failed: {e}")
            return None

    # ── internal: single-step execution ────────────────────────

    def _execute_one_step(self, instruction: str, step_index: int) -> StepResult:
        t0 = time.time()

        # 1. Capture BEFORE screenshot
        before_img, before_path = self.screenshot.capture()

        # 2. Resize for VLM
        vlm_target = _calc_vlm_size(before_img.width)
        vlm_img, scale = _resize_for_vlm(before_img, vlm_target)

        # 3. VLM analyzes screen → action
        vlm_resp = analyze_screen(vlm_img, instruction)

        # 4. Parse and scale coordinates
        vlm_w, vlm_h = vlm_img.size
        action = parse_action(vlm_resp.raw_response, vlm_w, vlm_h)
        action = _scale_action_coords(action, 1.0 / scale)
        print(f"[VLM] thought: {vlm_resp.thought}")
        print(f"[VLM] action: {vlm_resp.action} params={vlm_resp.params} conf={vlm_resp.confidence}")
        if scale != 1.0:
            print(f"[SCALE] native {before_img.width}px -> vlm {vlm_w}px, factor {1.0/scale:.2f}")

        # 5. Execute
        execute(action)
        time.sleep(0.5)

        # 6. Capture AFTER screenshot
        after_img, after_path = self.screenshot.capture()
        vlm_after_img, _ = _resize_for_vlm(after_img, vlm_target)

        # 7. Verify
        verdict = verify_step(vlm_img, vlm_after_img, instruction)

        # 8. Record
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
            step_index=step_index,
            instruction=instruction,
            action=action,
            verdict_passed=verdict.passed,
            verdict_reason=verdict.reason,
            before_path=before_path,
            after_path=after_path,
            vlm_raw=vlm_resp.raw_response,
            elapsed_ms=elapsed,
        )
