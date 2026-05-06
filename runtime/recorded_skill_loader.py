from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class RecordedSkillParamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "string"
    required: bool = False
    description: str | None = None


class RecordedSkillMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str
    intent: str
    tags: list[str] = Field(default_factory=list)
    status: str = "experimental"
    side_effect: bool
    success_rate: float | None = None


class RecordedSkillStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    wait_after: float | None = None
    save_as: str | None = None


class RecordedSkillComposeRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    params: dict[str, Any] = Field(default_factory=dict)


class RecordedSkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str = "recorded_skill"
    version: int
    metadata: RecordedSkillMetadata
    params: dict[str, RecordedSkillParamSpec] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    steps: list[RecordedSkillStep] = Field(default_factory=list)
    composed_of: list[RecordedSkillComposeRef] | None = None
    verification: Any | None = None

    source_path: str | None = None

    def required_params(self) -> set[str]:
        return {k for k, v in self.params.items() if bool(v.required)}

    def is_composed(self) -> bool:
        return bool(self.composed_of)


class RecordedSkillLoader:
    def load_path(self, path: str | Path) -> RecordedSkillDefinition:
        p = Path(path)
        raw = p.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError(f"recorded skill yaml must be a mapping: {p}")
        skill = RecordedSkillDefinition.model_validate(data)
        if skill.type != "recorded_skill":
            raise ValueError(f"invalid recorded skill type '{skill.type}' in: {p}")
        return skill.model_copy(update={"source_path": str(p.as_posix())})

    def load_dir(self, root_dir: str | Path) -> list[RecordedSkillDefinition]:
        root = Path(root_dir)
        if not root.exists():
            return []
        skills: list[RecordedSkillDefinition] = []
        for p in sorted(root.rglob("*.yaml")):
            skills.append(self.load_path(p))
        return skills


__all__ = [
    "RecordedSkillLoader",
    "RecordedSkillDefinition",
    "RecordedSkillStep",
    "RecordedSkillMetadata",
    "RecordedSkillParamSpec",
    "RecordedSkillComposeRef",
]

