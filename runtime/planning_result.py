from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class MissingCapabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["missing_capability"] = "missing_capability"
    product: str
    intent: str
    required_params: list[str] = Field(default_factory=list)
    current_state: list[str] = Field(default_factory=list)
    missing_reason: str
    missing_reason_code: str | None = None
    suggested_recorded_skill_id: str | None = None
    suggested_preconditions: list[str] = Field(default_factory=list)
    suggested_postconditions: list[str] = Field(default_factory=list)


class RecordedPlanSkillStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["recorded_skill"] = "recorded_skill"
    product: str
    intent: str
    recorded_skill_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    side_effect: bool = False


RecordedPlanStep = Union[RecordedPlanSkillStep, MissingCapabilityResult]


class RecordedPlanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["recorded_plan"] = "recorded_plan"
    product: str
    intent: str
    steps: list[RecordedPlanStep] = Field(default_factory=list)
    current_state: list[str] = Field(default_factory=list)
    complete: bool
    incomplete_reason: str | None = None


__all__ = [
    "MissingCapabilityResult",
    "RecordedPlanSkillStep",
    "RecordedPlanStep",
    "RecordedPlanResult",
]

