from __future__ import annotations

from pathlib import Path

from runtime.context import RunContext
from skills._helpers import config_get
from tools.base import BaseTool
from tools.gui._helpers import get_provider
from tools.schema import ToolResult, ToolSpec


def _resolve_path(raw: str, context: RunContext) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (Path(context.artifacts_dir) / p).resolve()


class VlmFindChatCandidateTool(BaseTool):
    spec = ToolSpec(
        name="vlm.find_chat_candidate",
        description="Use VLM to find the most likely Feishu chat candidate bbox/click point on Ctrl+K search results page.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "chat_name": {"type": "string"},
                "search_box_max_y": {"type": "integer"},
                "timeout_seconds": {"type": "integer"},
            },
            "required": ["path", "chat_name"],
        },
        output_schema={"type": "object"},
        timeout=90,
        retryable=True,
        side_effect=False,
    )

    def execute(self, params: dict, context: RunContext) -> ToolResult:
        try:
            provider = get_provider(context, "vlm")
            path = _resolve_path(str(params["path"]), context)
            chat_name = str(params["chat_name"])
            search_box_max_y = params.get("search_box_max_y")
            sb_y: int | None
            if search_box_max_y is None:
                # Default guard rail: exclude the Ctrl+K search box + filter chips region.
                # Use config ratio when available; otherwise use a conservative default.
                ratio = config_get(context, "im.search_box_region_max_y_ratio", 0.12)
                try:
                    ratio_f = float(ratio)
                except Exception:
                    ratio_f = 0.12
                # Ensure a minimum guard to cover the filter chip row in Ctrl+K overlay.
                ratio_f = max(0.14, min(0.35, ratio_f))
                try:
                    from PIL import Image  # type: ignore

                    with Image.open(path) as im:
                        sb_y = int(float(im.height) * ratio_f)
                except Exception:
                    sb_y = None
            else:
                sb_y = int(search_box_max_y)
            timeout_seconds = int(params.get("timeout_seconds", 30))
            out = provider.find_chat_candidate(path, chat_name=chat_name, search_box_max_y=sb_y, timeout_seconds=timeout_seconds)
            evidence = [str(path)] + list(out.get("evidence") or [])
            success = bool(out.get("success"))
            bbox = out.get("bbox")
            click_point = out.get("click_point")
            reason = out.get("reason")

            # Post-validate: never allow clicking inside excluded top region.
            if success and sb_y is not None and isinstance(click_point, (list, tuple)) and len(click_point) == 2:
                try:
                    y = int(float(click_point[1]))
                except Exception:
                    y = -1
                if y >= 0 and y <= int(sb_y):
                    evidence.append(f"guard:click_point_in_search_box:y={y}<=sb_y={int(sb_y)}")
                    # If bbox is valid and below the guard, snap to bbox center.
                    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                        try:
                            x1, y1, x2, y2 = [int(float(v)) for v in bbox]
                            cy = int((y1 + y2) / 2)
                            cx = int((x1 + x2) / 2)
                            if cy > int(sb_y):
                                click_point = [cx, cy]
                                evidence.append("guard:snap_click_point_to_bbox_center")
                            else:
                                success = False
                                reason = "click_point invalid (inside search box region)"
                        except Exception:
                            success = False
                            reason = "click_point invalid (inside search box region)"
                    else:
                        success = False
                        reason = "click_point invalid (inside search box region)"

            return ToolResult(
                success=success,
                data={"bbox": bbox, "click_point": click_point, "reason": reason, "chat_name": chat_name, "search_box_max_y": sb_y},
                evidence=evidence,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


__all__ = ["VlmFindChatCandidateTool"]
