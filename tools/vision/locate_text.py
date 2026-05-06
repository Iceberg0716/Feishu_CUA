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


def _center_from_bbox(bbox: object) -> list[int] | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(float(v)) for v in bbox)
    except Exception:
        return None
    return [int((x1 + x2) / 2), int((y1 + y2) / 2)]


class LocateTextTool(BaseTool):
    spec = ToolSpec(
        name="vision.locate_text",
        description="Locate target text in an image using OCR.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "text": {"type": "string"},
                "case_sensitive": {"type": "boolean"},
                "mode": {"type": "string", "enum": ["contains", "equals"]},
                "min_confidence": {"type": "number"},
            },
            "required": ["path", "text"],
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
            target = str(params["text"])
            case_sensitive = bool(params.get("case_sensitive", False))
            mode = str(params.get("mode", "contains"))
            min_conf = float(params.get("min_confidence", 0.0))

            items = provider.extract_text(path)
            matches: list[dict] = []
            for item in items:
                text = str(item.get("text") or "")
                conf = item.get("confidence")
                try:
                    conf_f = float(conf) if conf is not None else None
                except Exception:
                    conf_f = None
                if conf_f is not None and conf_f < min_conf:
                    continue

                lhs = text if case_sensitive else text.lower()
                rhs = target if case_sensitive else target.lower()
                ok = lhs == rhs if mode == "equals" else rhs in lhs
                if not ok:
                    continue

                bbox = item.get("bbox")
                match: dict = {"text": text, "confidence": conf_f, "bbox": bbox}
                center = _center_from_bbox(bbox)
                if center is not None:
                    match["center"] = center
                matches.append(match)

            found = bool(matches)
            evidence = [str(path), f"locate_text:{target}", f"matches:{len(matches)}"]
            return ToolResult(success=found, data={"path": str(path), "found": found, "matches": matches}, evidence=evidence)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = ["LocateTextTool"]

