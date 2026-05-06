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


class TextVisibleTool(BaseTool):
    spec = ToolSpec(
        name="verify.text_visible",
        description="Verify whether given text is visible in an image using OCR.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}, "text": {"type": "string"}, "case_sensitive": {"type": "boolean"}},
            "required": ["path", "text"],
        },
        output_schema={"type": "object"},
        timeout=60,
        retryable=True,
        side_effect=False,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        path = _resolve_path(str(params["path"]), context)
        target = str(params["text"])
        case_sensitive = bool(params.get("case_sensitive", False))
        evidence = [str(path), f"verify_text:{target}"]

        # Prefer OCR when available; fall back to VLM if OCR provider is not configured.
        ocr_error: str | None = None
        try:
            provider = get_provider(context, "ocr")
            items = provider.extract_text(path)
            text = "\n".join([str(i.get("text") or "").strip() for i in items if str(i.get("text") or "").strip()])
            haystack = text if case_sensitive else text.lower()
            needle = target if case_sensitive else target.lower()
            ok = needle in haystack
            if ok:
                evidence.append("visible:true")
                if text:
                    snippet = text if len(text) <= 200 else (text[:200] + "...")
                    evidence.append(f"ocr:{snippet}")
                return ToolResult(success=True, data={"path": str(path), "text": target, "method": "ocr"}, evidence=evidence, confidence=0.8)
            evidence.append("visible:false")
            return ToolResult(success=False, data={"path": str(path), "text": target, "method": "ocr"}, error="text not visible", evidence=evidence)
        except KeyError:
            pass
        except Exception as exc:
            # OCR can be flaky across environments (Paddle/PaddleOCR versions, CPU intrinsics, etc.).
            # Keep evidence, then fall back to VLM if configured.
            ocr_error = str(exc)
            evidence.append(f"ocr_error:{ocr_error}")

        try:
            vlm = get_provider(context, "vlm")
            out = vlm.judge_state(path, expectation=f"Text '{target}' is visible on the screen.")
            evidence += list(out.get("evidence") or [])
            if out.get("success"):
                evidence.append("visible:true")
                return ToolResult(success=True, data={"path": str(path), "text": target, "method": "vlm", "reason": out.get("reason")}, evidence=evidence, confidence=out.get("confidence"))
            evidence.append("visible:false")
            return ToolResult(success=False, data={"path": str(path), "text": target, "method": "vlm", "reason": out.get("reason")}, error="text not visible", evidence=evidence, confidence=out.get("confidence"))
        except Exception as exc:
            err = str(exc)
            if ocr_error:
                err = f"ocr failed ({ocr_error}); vlm failed ({err})"
            return ToolResult(success=False, error=err, evidence=evidence)


__all__ = ["TextVisibleTool"]
