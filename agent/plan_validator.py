from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from runtime.recorded_skill_registry import RecordedSkillRegistry


class ResolvedSubgoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str
    intent: str
    params: dict[str, Any] = Field(default_factory=dict)
    recorded_skill_id: str
    side_effect: bool = False


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "ok",
        "missing_capability",
        "missing_params",
        "clarification_required",
        "rejected",
    ]
    reason: str | None = None
    resolved_steps: list[ResolvedSubgoal] = Field(default_factory=list)
    confidence: float | None = None


_BANNED_SUBSTRINGS = [
    "gui.click",
    "gui.hotkey",
    "gui.type_text",
    "pyautogui",
    "pywinauto",
    "provider.",
    "tool_registry",
]

_COORD_KEY_RE = re.compile(r"^(x|y|xy|coord|coords|coordinate|coordinates|point|position)$", re.IGNORECASE)
_COORD_VALUE_RE = re.compile(r"\b\d{2,}\s*,\s*\d{2,}\b")

_COMPOSITE_SUBGOAL_SEQUENCES: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("im", "send_message"): [("im", "open_chat"), ("im", "send_text")],
    ("im", "send_emoji"): [("im", "open_chat"), ("im", "send_emoji")],
    ("im", "mention_member"): [("im", "open_chat"), ("im", "mention_member")],
}


def _walk_json(obj: Any) -> list[tuple[str, Any]]:
    """
    Flattens a JSON-like structure into (path, value) pairs for scanning.
    """
    out: list[tuple[str, Any]] = []

    def rec(v: Any, path: str) -> None:
        out.append((path, v))
        if isinstance(v, dict):
            for k, vv in v.items():
                rec(vv, f"{path}.{k}" if path else str(k))
        elif isinstance(v, list):
            for i, vv in enumerate(v):
                rec(vv, f"{path}[{i}]")

    rec(obj, "")
    return out


class PlanValidator:
    def __init__(self, *, registry: RecordedSkillRegistry) -> None:
        self._registry = registry

    def validate(
        self,
        plan: dict[str, Any],
        *,
        initial_state: list[str] | None = None,
    ) -> ValidationResult:
        allowed_top = {"status", "product", "intent", "params", "subgoals", "confidence"}
        extra_top = sorted([k for k in plan.keys() if k not in allowed_top])
        if extra_top:
            return ValidationResult(status="rejected", reason=f"extra keys not allowed at top-level: {','.join(extra_top)}")

        # Scan: reject any tool/coord/provider content (defense-in-depth).
        for path, value in _walk_json(plan):
            if _COORD_KEY_RE.match(path.rsplit(".", 1)[-1] if path else ""):
                return ValidationResult(status="rejected", reason=f"coordinate-like key is not allowed: {path}")
            if isinstance(value, str):
                lowered = value.lower()
                for banned in _BANNED_SUBSTRINGS:
                    if banned in lowered:
                        return ValidationResult(status="rejected", reason=f"banned content in plan: {banned}")
                if _COORD_VALUE_RE.search(value):
                    return ValidationResult(status="rejected", reason="coordinate-like value is not allowed")

        status = str(plan.get("status") or "").strip().lower()
        # Some LLMs emit "ready" for a completed plan. Normalize it to "ok" to avoid
        # brittle failures while still enforcing strict schema and tool bans.
        if status == "ready":
            status = "ok"
        if status and status != "ok":
            # Respect model-declared missing/clarification status, but still keep it safe.
            if status in {"missing_capability", "clarification_required", "missing_params"}:
                return ValidationResult(status=status, reason="llm_declared_" + status)
            return ValidationResult(status="rejected", reason=f"invalid status: {status}")

        product = str(plan.get("product") or "").strip().lower()
        intent = str(plan.get("intent") or "").strip()
        if not product or not intent:
            return ValidationResult(status="missing_params", reason="missing product/intent")

        confidence = plan.get("confidence")
        try:
            conf_f = float(confidence) if confidence is not None else None
        except Exception:
            conf_f = None

        raw_subgoals = plan.get("subgoals") or []
        if not isinstance(raw_subgoals, list) or not raw_subgoals:
            return ValidationResult(status="missing_params", reason="subgoals is required and must be a non-empty list")

        expected_seq = _COMPOSITE_SUBGOAL_SEQUENCES.get((product, intent))
        if expected_seq is not None:
            if len(raw_subgoals) != len(expected_seq):
                return ValidationResult(
                    status="rejected",
                    reason=(
                        f"composite intent requires exact subgoal sequence for {product}/{intent}: "
                        + " -> ".join([f"{p}/{i}" for p, i in expected_seq])
                    ),
                    confidence=conf_f,
                )
            for idx, (exp_product, exp_intent) in enumerate(expected_seq):
                sg = raw_subgoals[idx]
                if not isinstance(sg, dict):
                    return ValidationResult(status="rejected", reason=f"subgoals[{idx}] must be an object", confidence=conf_f)
                sg_product = str(sg.get("product") or "").strip().lower()
                sg_intent = str(sg.get("intent") or "").strip()
                if sg_product != exp_product or sg_intent != exp_intent:
                    return ValidationResult(
                        status="rejected",
                        reason=(
                            f"composite intent requires exact subgoal sequence for {product}/{intent}: "
                            + " -> ".join([f"{p}/{i}" for p, i in expected_seq])
                        ),
                        confidence=conf_f,
                    )

        state = set(initial_state or ["feishu_window_available"])
        resolved: list[ResolvedSubgoal] = []

        for idx, sg in enumerate(raw_subgoals):
            if not isinstance(sg, dict):
                return ValidationResult(status="rejected", reason=f"subgoals[{idx}] must be an object")
            allowed_sg = {"product", "intent", "params"}
            extra_sg = sorted([k for k in sg.keys() if k not in allowed_sg])
            if extra_sg:
                return ValidationResult(status="rejected", reason=f"extra keys not allowed in subgoals[{idx}]: {','.join(extra_sg)}")

            sg_product = str(sg.get("product") or "").strip().lower()
            sg_intent = str(sg.get("intent") or "").strip()
            sg_params = sg.get("params") or {}
            if not isinstance(sg_params, dict):
                return ValidationResult(status="rejected", reason=f"subgoals[{idx}].params must be an object")

            if not sg_product or not sg_intent:
                return ValidationResult(status="missing_params", reason=f"subgoals[{idx}] missing product/intent")

            compat = self._registry.find_compatible(sg_product, sg_intent, sg_params, state)
            best = next((c for c in compat if c.compatible), None)
            if best is None:
                if not compat:
                    return ValidationResult(
                        status="missing_capability",
                        reason=f"no recorded skill for product={sg_product} intent={sg_intent}",
                        confidence=conf_f,
                    )
                # Diagnose: missing params vs preconditions.
                top = compat[0]
                missing_params: set[str] = set()
                unmet_pre: set[str] = set()
                for r in compat:
                    for reason in r.reasons:
                        if reason.startswith("missing_params:"):
                            missing_params |= set([p for p in reason.split(":", 1)[1].split(",") if p])
                        if reason.startswith("unmet_preconditions:"):
                            unmet_pre |= set([p for p in reason.split(":", 1)[1].split(",") if p])
                if missing_params:
                    return ValidationResult(
                        status="missing_params",
                        reason=f"missing required params for {sg_product}/{sg_intent}: {','.join(sorted(missing_params))}",
                        confidence=conf_f,
                    )
                if unmet_pre:
                    return ValidationResult(
                        status="missing_capability",
                        reason=(
                            f"no compatible recorded skill for {sg_product}/{sg_intent} "
                            f"(unmet_preconditions: {','.join(sorted(unmet_pre))})"
                        ),
                        confidence=conf_f,
                    )
                return ValidationResult(
                    status="missing_capability",
                    reason=f"no compatible recorded skill for {sg_product}/{sg_intent}",
                    confidence=conf_f,
                )

            skill = best.skill
            resolved.append(
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

        return ValidationResult(status="ok", resolved_steps=resolved, confidence=conf_f)

    @staticmethod
    def to_json(result: ValidationResult) -> str:
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


__all__ = ["PlanValidator", "ValidationResult", "ResolvedSubgoal"]
