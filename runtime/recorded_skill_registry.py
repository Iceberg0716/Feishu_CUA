from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.recorded_skill_loader import RecordedSkillDefinition


def _status_rank(status: str) -> int:
    return 0 if str(status).lower() == "stable" else 1


@dataclass(frozen=True, slots=True)
class Compatibility:
    skill: RecordedSkillDefinition
    compatible: bool
    reasons: list[str]


class RecordedSkillRegistry:
    def __init__(self, skills: list[RecordedSkillDefinition] | None = None) -> None:
        self._skills: dict[str, RecordedSkillDefinition] = {}
        self._all: list[RecordedSkillDefinition] = []
        if skills:
            for s in skills:
                self.register(s)

    def register(self, skill: RecordedSkillDefinition) -> None:
        if skill.id in self._skills:
            raise ValueError(f"RecordedSkill already registered: {skill.id}")
        self._skills[skill.id] = skill
        self._all.append(skill)

    def list(self) -> list[RecordedSkillDefinition]:
        return sorted(self._all, key=lambda s: s.id)

    def get(self, skill_id: str) -> RecordedSkillDefinition:
        if skill_id not in self._skills:
            raise KeyError(f"RecordedSkill not found: {skill_id}")
        return self._skills[skill_id]

    def find_by_intent(self, product: str, intent: str) -> list[RecordedSkillDefinition]:
        out = [s for s in self._all if s.metadata.product == product and s.metadata.intent == intent]
        return self._sorted_preferred(out)

    def find_by_postcondition(self, postcondition: str) -> list[RecordedSkillDefinition]:
        out = [s for s in self._all if postcondition in (s.postconditions or [])]
        return self._sorted_preferred(out)

    def find_compatible(
        self,
        product: str,
        intent: str,
        params: dict[str, Any] | None,
        current_state: list[str] | set[str] | None,
    ) -> list[Compatibility]:
        given = params or {}
        state = set(current_state or [])

        candidates = self.find_by_intent(product, intent)
        results: list[Compatibility] = []
        for s in candidates:
            reasons: list[str] = []
            missing = sorted([p for p in s.required_params() if p not in given])
            if missing:
                reasons.append("missing_params:" + ",".join(missing))
            unmet = sorted([c for c in (s.preconditions or []) if c not in state])
            if unmet:
                reasons.append("unmet_preconditions:" + ",".join(unmet))
            results.append(Compatibility(skill=s, compatible=not reasons, reasons=reasons))

        results.sort(
            key=lambda r: (
                0 if r.compatible else 1,
                _status_rank(r.skill.metadata.status),
                -(float(r.skill.metadata.success_rate) if r.skill.metadata.success_rate is not None else 0.0),
                -int(r.skill.version),
                r.skill.id,
            )
        )
        return results

    def _sorted_preferred(self, skills: list[RecordedSkillDefinition]) -> list[RecordedSkillDefinition]:
        skills = list(skills)
        skills.sort(
            key=lambda s: (
                _status_rank(s.metadata.status),
                -(float(s.metadata.success_rate) if s.metadata.success_rate is not None else 0.0),
                -int(s.version),
                s.id,
            )
        )
        return skills


__all__ = ["RecordedSkillRegistry", "Compatibility"]

