from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["skill"]
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    expect: dict[str, Any] | None = None


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)


__all__ = ["Plan", "PlanStep"]

