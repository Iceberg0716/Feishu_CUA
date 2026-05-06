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


class OcrExtractTool(BaseTool):
    spec = ToolSpec(
        name="vision.ocr_extract",
        description="Run OCR on an image and return extracted text items.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        output_schema={"type": "object"},
        timeout=60,
        retryable=True,
        side_effect=False,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "ocr")
            path = _resolve_path(str(params["path"]), context)
            items = provider.extract_text(path)
            text = "\n".join([str(i.get("text") or "").strip() for i in items if str(i.get("text") or "").strip()])
            evidence = [str(path)]
            if text:
                snippet = text if len(text) <= 200 else (text[:200] + "...")
                evidence.append(f"ocr:{snippet}")
            return ToolResult(success=True, data={"path": str(path), "items": items, "text": text}, evidence=evidence)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = ["OcrExtractTool"]

