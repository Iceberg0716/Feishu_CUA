from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.registry import ToolRegistry


def _default_tool_registry() -> "ToolRegistry":
    from tools.registry import ToolRegistry

    return ToolRegistry()


@dataclass(slots=True)
class RunContext:
    run_id: str
    artifacts_dir: Path
    tool_registry: "ToolRegistry" = field(default_factory=_default_tool_registry)
    metadata: dict[str, Any] = field(default_factory=dict)
