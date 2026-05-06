from __future__ import annotations

from abc import ABC, abstractmethod

from tools.schema import ToolResult, ToolSpec
from runtime.context import RunContext


class BaseTool(ABC):
    spec: ToolSpec

    @abstractmethod
    def execute(self, params: dict, context: RunContext) -> ToolResult:
        raise NotImplementedError

