from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StepLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    step_type: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    success: bool
    started_at: datetime
    ended_at: datetime
    error: str | None = None
    evidence: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    goal: str
    success: bool
    started_at: datetime
    ended_at: datetime
    steps: list[StepLog] = Field(default_factory=list)
    error: str | None = None
    evidence: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: datetime
    ended_at: datetime
    cases: list[CaseResult] = Field(default_factory=list)

    @property
    def total_cases(self) -> int:  # pragma: no cover
        return len(self.cases)

    @property
    def passed(self) -> int:  # pragma: no cover
        return sum(1 for c in self.cases if c.success)

    @property
    def failed(self) -> int:  # pragma: no cover
        return sum(1 for c in self.cases if not c.success)
