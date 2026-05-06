from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.llm_planner import LLMPlanner
from agent.plan_validator import PlanValidator, ResolvedSubgoal, ValidationResult
from providers.errors import ProviderDependencyError
from providers.text_llm_provider import OpenAICompatibleTextLLMProvider
from runtime.config import load_yaml_config
from runtime.context import RunContext
from runtime.recorded_skill_loader import RecordedSkillLoader
from runtime.recorded_skill_registry import RecordedSkillRegistry
from skills.recorded import RecordedSkillExecutor
from tools.defaults import build_default_tool_registry


@dataclass(frozen=True, slots=True)
class NaturalLanguageRunResult:
    success: bool
    status: str
    error: str | None = None
    evidence: list[str] | None = None
    resolved_plan: dict[str, Any] | None = None


def _build_recorded_registry() -> RecordedSkillRegistry:
    loader = RecordedSkillLoader()
    skills = loader.load_dir("recorded_skills")
    return RecordedSkillRegistry(skills)


def _build_text_llm_provider(config: dict[str, Any]) -> OpenAICompatibleTextLLMProvider:
    llm_cfg = config.get("llm") if isinstance(config.get("llm"), dict) else {}
    provider = str(llm_cfg.get("provider") or "openai_compatible").lower()
    if provider not in {"dashscope", "openai_compatible"}:
        raise ProviderDependencyError(f"unsupported llm provider: {provider}")

    base_url = str(llm_cfg.get("base_url") or "").strip()
    model = str(llm_cfg.get("model") or "").strip()
    api_key = str(llm_cfg.get("api_key") or "").strip()

    missing: list[str] = []
    if not base_url:
        missing.append("llm.base_url")
    if not model:
        missing.append("llm.model")
    if not api_key:
        missing.append("llm.api_key")
    if missing:
        raise ProviderDependencyError(
            "LLM config missing "
            + ", ".join(missing)
            + " (set in `config.yaml` and/or `.env`, e.g. LLM_BASE_URL/LLM_MODEL/LLM_API_KEY)"
        )

    return OpenAICompatibleTextLLMProvider(base_url=base_url, api_key=api_key, model=model)


class NaturalLanguageRunner:
    def __init__(self, *, config_path: str = "config.yaml") -> None:
        self._config_path = config_path

    def run(self, instruction: str) -> NaturalLanguageRunResult:
        print("Natural Language Instruction:")
        print(instruction)
        print("")
        try:
            config = load_yaml_config(self._config_path)
        except Exception as exc:
            return NaturalLanguageRunResult(success=False, status="error", error=f"config load failed: {exc}")

        registry = _build_recorded_registry()
        validator = PlanValidator(registry=registry)

        try:
            llm_provider = _build_text_llm_provider(config)
        except ProviderDependencyError as exc:
            return NaturalLanguageRunResult(success=False, status="error", error=str(exc))

        planner = LLMPlanner(llm=llm_provider)

        # Step-by-step mode:
        # 1) ask LLM to parse task intent + params
        # 2) execute a fixed composite policy (e.g. IM send_message => open_chat then send_text)
        # 3) before each step, ask LLM to output exactly one next subgoal (params only)
        # 4) resolve that subgoal to a compatible recorded skill using registry+state, then execute.
        try:
            task = planner.plan_intent(instruction=instruction, registry=registry)
        except Exception as exc:
            return NaturalLanguageRunResult(success=False, status="error", error=f"llm intent parse failed: {exc}")

        task_dict = task.model_dump()
        status = str(task.status or "").strip().lower()
        if status and status != "ok":
            return NaturalLanguageRunResult(
                success=False,
                status=status,
                error="llm_declared_" + status,
                resolved_plan={"llm_task": task_dict},
            )

        product = str(task.product or "").strip().lower()
        intent = str(task.intent or "").strip()
        known_params = dict(task.params or {})

        composite_sequences: dict[tuple[str, str], list[tuple[str, str]]] = {
            ("im", "send_message"): [("im", "open_chat"), ("im", "send_text")],
            ("im", "send_emoji"): [("im", "open_chat"), ("im", "send_emoji")],
            ("im", "mention_member"): [("im", "open_chat"), ("im", "mention_member")],
        }

        seq = composite_sequences.get((product, intent))
        stepwise_debug: dict[str, Any] = {"llm_task": task_dict, "llm_steps": []}

        # Fallback to legacy full-plan mode for unsupported intents (keeps compatibility).
        if seq is None:
            try:
                llm_plan = planner.plan(instruction=instruction, registry=registry)
            except Exception as exc:
                return NaturalLanguageRunResult(success=False, status="error", error=f"llm plan failed: {exc}")

            plan_dict = llm_plan.model_dump()
            validation = validator.validate(plan_dict)
            if validation.status != "ok":
                return NaturalLanguageRunResult(
                    success=False,
                    status=validation.status,
                    error=validation.reason,
                    resolved_plan={"validation": validation.model_dump(), "llm_plan": plan_dict},
                )

            print(format_plan_summary(validation), end="")
            print("Executing...")
            resolved_plan = {"llm_plan": plan_dict, "validation": validation.model_dump()}
            resolved_steps = list(validation.resolved_steps)
        else:
            # Build a resolved step list via per-step LLM calls.
            resolved_steps = []
            state: set[str] = {"feishu_window_available"}
            last_step: dict[str, Any] | None = None

            for idx, (req_product, req_intent) in enumerate(seq, start=1):
                try:
                    next_plan = planner.plan_next_subgoal(
                        instruction=instruction,
                        registry=registry,
                        required_product=req_product,
                        required_intent=req_intent,
                        known_params=known_params,
                        current_state=sorted(state),
                        last_step=last_step,
                    )
                except Exception as exc:
                    return NaturalLanguageRunResult(
                        success=False,
                        status="error",
                        error=f"llm next-step plan failed at step={idx} ({req_product}/{req_intent}): {exc}",
                        resolved_plan=stepwise_debug,
                    )

                next_plan_dict = next_plan.model_dump()
                stepwise_debug["llm_steps"].append(next_plan_dict)
                sp_status = str(next_plan.status or "").strip().lower()
                if sp_status and sp_status != "ok":
                    return NaturalLanguageRunResult(
                        success=False,
                        status=sp_status,
                        error="llm_declared_" + sp_status,
                        resolved_plan=stepwise_debug,
                    )

                sg = next_plan.subgoal
                if sg is None:
                    return NaturalLanguageRunResult(
                        success=False,
                        status="missing_params",
                        error=f"llm returned no subgoal for step={idx}",
                        resolved_plan=stepwise_debug,
                    )

                sg_product = str(sg.product or "").strip().lower()
                sg_intent = str(sg.intent or "").strip()
                if sg_product != req_product or sg_intent != req_intent:
                    return NaturalLanguageRunResult(
                        success=False,
                        status="rejected",
                        error=f"llm returned wrong subgoal for step={idx}: got {sg_product}/{sg_intent}, want {req_product}/{req_intent}",
                        resolved_plan=stepwise_debug,
                    )

                sg_params = dict(sg.params or {})
                compat = registry.find_compatible(sg_product, sg_intent, sg_params, state)
                best = next((c for c in compat if c.compatible), None)
                if best is None:
                    # Diagnose: missing params vs unmet preconditions vs missing capability.
                    missing_params: set[str] = set()
                    unmet_pre: set[str] = set()
                    for r in compat:
                        for reason in r.reasons:
                            if reason.startswith("missing_params:"):
                                missing_params |= set([p for p in reason.split(":", 1)[1].split(",") if p])
                            if reason.startswith("unmet_preconditions:"):
                                unmet_pre |= set([p for p in reason.split(":", 1)[1].split(",") if p])

                    if not compat:
                        return NaturalLanguageRunResult(
                            success=False,
                            status="missing_capability",
                            error=f"no recorded skill for product={sg_product} intent={sg_intent}",
                            resolved_plan=stepwise_debug,
                        )
                    if missing_params:
                        return NaturalLanguageRunResult(
                            success=False,
                            status="missing_params",
                            error=f"missing required params for {sg_product}/{sg_intent}: {','.join(sorted(missing_params))}",
                            resolved_plan=stepwise_debug,
                        )
                    if unmet_pre:
                        return NaturalLanguageRunResult(
                            success=False,
                            status="missing_capability",
                            error=f"no compatible recorded skill for {sg_product}/{sg_intent} (unmet_preconditions: {','.join(sorted(unmet_pre))})",
                            resolved_plan=stepwise_debug,
                        )
                    return NaturalLanguageRunResult(
                        success=False,
                        status="missing_capability",
                        error=f"no compatible recorded skill for {sg_product}/{sg_intent}",
                        resolved_plan=stepwise_debug,
                    )

                skill = best.skill
                resolved_steps.append(
                    ResolvedSubgoal(
                        product=sg_product,
                        intent=sg_intent,
                        params={k: sg_params.get(k) for k in sorted(skill.required_params()) if k in sg_params},
                        recorded_skill_id=skill.id,
                        side_effect=bool(skill.metadata.side_effect),
                    )
                )
                for post in skill.postconditions or []:
                    state.add(post)
                last_step = {"step": idx, "product": sg_product, "intent": sg_intent, "resolved_skill_id": skill.id, "status": "planned"}

            validation = ValidationResult(status="ok", resolved_steps=resolved_steps)
            print(format_plan_summary(validation), end="")
            print("Executing...")
            resolved_plan = {"stepwise": stepwise_debug, "resolved_steps": [s.model_dump() for s in resolved_steps]}

        tool_registry = build_default_tool_registry(config)
        executor = RecordedSkillExecutor(tool_registry=tool_registry, skill_registry=registry)

        run_id = "nl_" + datetime.now().strftime("%Y-%m-%d_%H%M%S")
        artifacts = Path(str(config.get("runtime", {}).get("run_dir") or "artifacts/runs")) / run_id
        artifacts.mkdir(parents=True, exist_ok=True)

        from runtime.providers import build_providers

        providers = build_providers(config)
        ctx = RunContext(
            run_id=run_id,
            artifacts_dir=artifacts,
            tool_registry=tool_registry,
            metadata={"config": config, "providers": providers, "nl_instruction": instruction},
        )

        evidence: list[str] = []
        # Execute sequentially, stop on first failure.
        for i, step in enumerate(resolved_steps, start=1):
            print(f"Step {i}: {step.intent} ... ", end="")
            try:
                skill = registry.get(step.recorded_skill_id)
            except Exception as exc:
                print("FAIL")
                return NaturalLanguageRunResult(
                    success=False,
                    status="error",
                    error=f"resolved recorded skill not found: {step.recorded_skill_id} ({exc})",
                    evidence=evidence,
                    resolved_plan=resolved_plan,
                )
            res = executor.execute(skill, params=step.params, context=ctx)
            evidence.extend(list(res.evidence or []))
            if not res.success:
                print("FAIL")
                return NaturalLanguageRunResult(
                    success=False,
                    status="failed",
                    error=res.error or f"recorded skill failed: {step.recorded_skill_id}",
                    evidence=evidence,
                    resolved_plan=resolved_plan,
                )
            print("OK")

        print("")
        print("Result: SUCCESS")
        return NaturalLanguageRunResult(
            success=True,
            status="success",
            error=None,
            evidence=evidence,
            resolved_plan=resolved_plan,
        )


def format_plan_summary(validation: ValidationResult) -> str:
    lines: list[str] = ["Resolved Plan:"]
    for i, step in enumerate(validation.resolved_steps, start=1):
        params_str = ", ".join([f"{k}={v}" for k, v in step.params.items()])
        lines.append(f"{i}. {step.intent}")
        lines.append(f"   Skill: {step.recorded_skill_id}")
        lines.append(f"   Params: {params_str}" if params_str else "   Params: (none)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["NaturalLanguageRunner", "NaturalLanguageRunResult", "format_plan_summary"]
