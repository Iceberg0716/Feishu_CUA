from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from runtime.context import RunContext
from runtime.recorded_skill_loader import RecordedSkillDefinition, RecordedSkillLoader, RecordedSkillStep
from runtime.recorded_skill_registry import RecordedSkillRegistry
from runtime.template_renderer import TemplateRenderError, TemplateRenderer
from tools.registry import ToolRegistry
from tools.schema import ToolResult


@dataclass(slots=True)
class RecordedSkillRunResult:
    success: bool
    recorded_skill_id: str
    failed_step: str | None = None
    error: str | None = None
    evidence: list[dict[str, Any]] | None = None
    vars: dict[str, Any] | None = None


class RecordedSkillExecutor:
    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        skill_registry: RecordedSkillRegistry,
        loader: RecordedSkillLoader | None = None,
        renderer: TemplateRenderer | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._tools = tool_registry
        self._skills = skill_registry
        self._loader = loader or RecordedSkillLoader()
        self._renderer = renderer or TemplateRenderer()
        self._sleep = sleep

    def resolve(self, skill_id_or_path: str) -> RecordedSkillDefinition:
        if skill_id_or_path.endswith(".yaml") or skill_id_or_path.endswith(".yml"):
            return self._loader.load_path(skill_id_or_path)
        return self._skills.get(skill_id_or_path)

    def execute(
        self,
        skill: RecordedSkillDefinition,
        *,
        params: dict[str, Any],
        context: RunContext,
        start_step: str | None = None,
        end_step: str | None = None,
    ) -> RecordedSkillRunResult:
        evidence: list[dict[str, Any]] = []
        local_vars: dict[str, Any] = {}
        try:
            if skill.is_composed():
                return self._execute_composed(skill, params=params, context=context, evidence=evidence, vars=local_vars)
            return self._execute_steps(
                skill,
                params=params,
                context=context,
                steps=skill.steps,
                start_step=start_step,
                end_step=end_step,
                evidence=evidence,
                vars=local_vars,
            )
        except Exception as exc:
            return RecordedSkillRunResult(
                success=False,
                recorded_skill_id=skill.id,
                failed_step=None,
                error=str(exc),
                evidence=evidence,
                vars=local_vars,
            )

    def _execute_composed(
        self,
        skill: RecordedSkillDefinition,
        *,
        params: dict[str, Any],
        context: RunContext,
        evidence: list[dict[str, Any]],
        vars: dict[str, Any],
    ) -> RecordedSkillRunResult:
        if not skill.composed_of:
            return RecordedSkillRunResult(success=True, recorded_skill_id=skill.id, evidence=evidence, vars=vars)

        for idx, ref in enumerate(skill.composed_of, start=1):
            child = self._skills.get(ref.skill)
            rendered = self._renderer.render(ref.params, params=params, vars=vars)
            if not isinstance(rendered, dict):
                return RecordedSkillRunResult(
                    success=False,
                    recorded_skill_id=skill.id,
                    failed_step=f"composed_of[{idx}]",
                    error=f"composed params must render to a mapping for {ref.skill}",
                    evidence=evidence,
                    vars=vars,
                )
            res = self.execute(child, params=rendered, context=context)
            evidence.append(
                {
                    "recorded_skill_id": skill.id,
                    "recorded_step_id": f"composed_of[{idx}]",
                    "tool": "recorded.execute",
                    "success": bool(res.success),
                    "wait_after": None,
                    "save_as": None,
                    "child_skill_id": child.id,
                    "child_success": bool(res.success),
                    "child_failed_step": res.failed_step,
                    "child_error": res.error,
                }
            )
            if not res.success:
                return RecordedSkillRunResult(
                    success=False,
                    recorded_skill_id=skill.id,
                    failed_step=f"composed_of[{idx}]",
                    error=res.error or f"child skill failed: {child.id}",
                    evidence=evidence,
                    vars=vars,
                )
        return RecordedSkillRunResult(success=True, recorded_skill_id=skill.id, evidence=evidence, vars=vars)

    def _execute_steps(
        self,
        skill: RecordedSkillDefinition,
        *,
        params: dict[str, Any],
        context: RunContext,
        steps: list[RecordedSkillStep],
        start_step: str | None,
        end_step: str | None,
        evidence: list[dict[str, Any]],
        vars: dict[str, Any],
    ) -> RecordedSkillRunResult:
        started = start_step is None

        for step in steps:
            if not started:
                if step.id == start_step:
                    started = True
                else:
                    continue

            rendered_params = self._renderer.render(step.params, params=params, vars=vars)
            if not isinstance(rendered_params, dict):
                return RecordedSkillRunResult(
                    success=False,
                    recorded_skill_id=skill.id,
                    failed_step=step.id,
                    error=f"step params must render to a mapping: {step.id}",
                    evidence=evidence,
                    vars=vars,
                )

            tool_res = self._call_tool(step.tool, rendered_params, context=context)
            evidence.append(
                {
                    "recorded_skill_id": skill.id,
                    "recorded_step_id": step.id,
                    "tool": step.tool,
                    "success": bool(tool_res.success),
                    "wait_after": step.wait_after,
                    "save_as": step.save_as,
                    "tool_error": tool_res.error,
                    "tool_evidence": list(tool_res.evidence or []),
                }
            )

            if tool_res.success and step.save_as:
                vars[step.save_as] = tool_res.data

            if step.wait_after is not None and tool_res.success:
                wait_s = float(step.wait_after)
                if wait_s > 0:
                    self._sleep(wait_s)

            if not tool_res.success:
                return RecordedSkillRunResult(
                    success=False,
                    recorded_skill_id=skill.id,
                    failed_step=step.id,
                    error=tool_res.error or f"tool failed: {step.tool}",
                    evidence=evidence,
                    vars=vars,
                )

            if end_step is not None and step.id == end_step:
                break

        if start_step is not None and not started:
            return RecordedSkillRunResult(
                success=False,
                recorded_skill_id=skill.id,
                failed_step=None,
                error=f"start_step not found: {start_step}",
                evidence=evidence,
                vars=vars,
            )

        return RecordedSkillRunResult(success=True, recorded_skill_id=skill.id, evidence=evidence, vars=vars)

    def _call_tool(self, tool_name: str, params: dict[str, Any], *, context: RunContext) -> ToolResult:
        try:
            tool = self._tools.get(tool_name)
        except Exception as exc:
            return ToolResult(success=False, error=f"tool not found: {tool_name} ({exc})")

        try:
            return tool.execute(params, context)
        except TemplateRenderError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    @staticmethod
    def compute_side_effect(skill: RecordedSkillDefinition, registry: RecordedSkillRegistry) -> bool:
        if not skill.is_composed():
            return bool(skill.metadata.side_effect)
        if not skill.composed_of:
            return bool(skill.metadata.side_effect)
        return any(bool(registry.get(ref.skill).metadata.side_effect) for ref in skill.composed_of)


__all__ = ["RecordedSkillExecutor", "RecordedSkillRunResult"]

