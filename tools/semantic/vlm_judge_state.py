from __future__ import annotations

from pathlib import Path

from runtime.context import RunContext
from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec


def _resolve_path(raw: str, context: RunContext) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (Path(context.artifacts_dir) / p).resolve()


class VlmJudgeStateTool(BaseTool):
    spec = ToolSpec(
        name="vlm.judge_state",
        description="Use VLM to judge whether current UI state matches expectation.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}, "expectation": {"type": "string"}, "timeout_seconds": {"type": "integer"}},
            "required": ["path", "expectation"],
        },
        output_schema={"type": "object"},
        timeout=60,
        retryable=True,
        side_effect=False,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "vlm")
            path = _resolve_path(str(params["path"]), context)
            expectation = str(params["expectation"])
            timeout_seconds = int(params.get("timeout_seconds", 30))
            out = provider.judge_state(path, expectation=expectation, timeout_seconds=timeout_seconds)
            evidence = [str(path)] + list(out.get("evidence") or [])
            return ToolResult(
                success=bool(out.get("success")),
                data={"reason": out.get("reason"), "expectation": expectation},
                evidence=evidence,
                confidence=out.get("confidence"),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = ["VlmJudgeStateTool"]

