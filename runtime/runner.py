from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from agent.planner import RulePlanner
from agent.schemas import Plan
from runtime.context import RunContext
from runtime.logger import JsonlLogger
from runtime.models import CaseResult, RunResult, StepLog
from runtime.providers import build_providers
from runtime.testcases import load_testcase
from skills.defaults import build_default_skill_registry
from skills.registry import SkillRegistry
from tools.defaults import build_default_tool_registry
from tools.registry import ToolRegistry


def _now() -> datetime:
    return datetime.now()


class Runner:
    def __init__(
        self,
        *,
        config: dict[str, Any],
        artifacts_base: Path,
        providers: dict[str, Any] | None = None,
        tool_registry: ToolRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
        planner: RulePlanner | None = None,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._config = config
        self._artifacts_base = artifacts_base
        self._providers = providers
        self._tool_registry = tool_registry or build_default_tool_registry(self._config)
        self._skill_registry = skill_registry or build_default_skill_registry()
        self._planner = planner or RulePlanner()
        self._now = now

    def run_files(self, testcase_paths: list[str]) -> RunResult:
        started = self._now()
        run_id = started.strftime("%Y-%m-%d_%H%M%S")
        run_dir = (self._artifacts_base / run_id).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir = run_dir / "screenshots"
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        logger = JsonlLogger(logs_dir / "run.jsonl")

        providers = self._providers if self._providers is not None else build_providers(self._config)
        ctx = RunContext(
            run_id=run_id,
            artifacts_dir=run_dir,
            tool_registry=self._tool_registry,
            metadata={"providers": providers, "config": self._config},
        )

        cases: list[CaseResult] = []
        for i, path in enumerate(testcase_paths, start=1):
            tc = load_testcase(path)
            case = self._run_one(tc, ctx=ctx, screenshots_dir=screenshots_dir, logger=logger, case_index=i)
            cases.append(case)
            if not case.success:
                # Stop on first failure for MVP; can be made configurable.
                break

        ended = self._now()
        run = RunResult(run_id=run_id, started_at=started, ended_at=ended, cases=cases)
        (run_dir / "result.json").write_text(json.dumps(run.model_dump(), ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        return run

    def _run_one(self, testcase: dict[str, Any], *, ctx: RunContext, screenshots_dir: Path, logger: JsonlLogger, case_index: int) -> CaseResult:
        started = self._now()
        plan = self._planner.build_plan(testcase)

        step_logs: list[StepLog] = []
        overall_success = True
        error: str | None = None

        for idx, step in enumerate(plan.steps, start=1):
            s_started = self._now()
            before = self._take_screenshot(ctx, screenshots_dir, f"c{case_index:02d}_s{idx:02d}_{step.id}_before.png")
            attempt_success = False
            attempt_error: str | None = None
            attempt_evidence: list[str] = []
            attempt_result: dict[str, Any] = {}

            retry_times = int(self._config.get("runtime", {}).get("retry_times", 2) or 2)
            skill = None
            try:
                skill = self._skill_registry.get(step.name)
            except Exception:
                skill = None
            if getattr(skill, "side_effect", False):
                retry_times = int(self._config.get("runtime", {}).get("side_effect_retry_times", 0) or 0)
            for attempt in range(0, max(1, retry_times + 1)):
                res = self._execute_step(step, ctx)
                attempt_evidence = (before or []) + res.get("evidence", [])
                attempt_success = bool(res.get("success"))
                attempt_result = res.get("result", {})
                attempt_error = res.get("error")
                if attempt_success:
                    break
                if attempt < retry_times:
                    logger.write({"event": "retry", "case": plan.case_id, "step": step.id, "attempt": attempt + 1, "error": attempt_error})

            after = self._take_screenshot(ctx, screenshots_dir, f"c{case_index:02d}_s{idx:02d}_{step.id}_after.png")
            if after:
                attempt_evidence += after

            s_ended = self._now()
            step_log = StepLog(
                step_id=step.id,
                step_type=step.type,
                name=step.name,
                params=step.params,
                success=attempt_success,
                started_at=s_started,
                ended_at=s_ended,
                error=attempt_error,
                evidence=attempt_evidence,
                result=attempt_result,
            )
            step_logs.append(step_log)
            logger.write({"event": "step", "case": plan.case_id, "step": step_log.model_dump()})

            if not attempt_success:
                overall_success = False
                error = attempt_error or f"step failed: {step.id}"
                break

        ended = self._now()
        return CaseResult(
            case_id=plan.case_id,
            goal=plan.goal,
            success=overall_success,
            started_at=started,
            ended_at=ended,
            steps=step_logs,
            error=error,
            evidence=[e for s in step_logs for e in s.evidence],
            meta={"run_id": ctx.run_id, "run_dir": str(ctx.artifacts_dir), "testcase_id": testcase.get("id")},
        )

    def _execute_step(self, step: Any, ctx: RunContext) -> dict[str, Any]:
        if step.type != "skill":
            return {"success": False, "error": f"unsupported step type: {step.type}", "evidence": [], "result": {}}
        try:
            skill = self._skill_registry.get(step.name)
            res = skill.execute(step.params, ctx)
            return {
                "success": res.success,
                "error": res.error,
                "evidence": res.evidence,
                "result": res.data,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "evidence": [], "result": {}}

    def _take_screenshot(self, ctx: RunContext, screenshots_dir: Path, filename: str) -> list[str]:
        try:
            tool = ctx.tool_registry.get("screen.screenshot")
            res = tool.execute({"filename": filename, "subdir": "screenshots"}, ctx)
            if res.success:
                return list(res.evidence)
            return []
        except Exception:
            return []


__all__ = ["Runner", "Plan"]
