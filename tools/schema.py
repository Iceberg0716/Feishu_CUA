from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout: int = 30
    retryable: bool = True
    side_effect: bool = False


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float | None = None

