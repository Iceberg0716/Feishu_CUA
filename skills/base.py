from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from runtime.context import RunContext


class SkillResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    evidence: list[str] = Field(default_factory=list)


class BaseSkill(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]
    side_effect: bool = False

    @abstractmethod
    def execute(self, params: dict[str, Any], context: RunContext) -> SkillResult:
        raise NotImplementedError
