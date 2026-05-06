from __future__ import annotations

from pathlib import Path
from typing import Any

from providers.errors import ProviderActionError, ProviderDependencyError


def _bbox_from_polygon(polygon: Any) -> list[int] | None:
    if not isinstance(polygon, (list, tuple)) or not polygon:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for pt in polygon:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        try:
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
        except Exception:
            continue
    if not xs or not ys:
        return None
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


class PaddleOCRProvider:
    def __init__(
        self,
        ocr_engine: Any | None = None,
        *,
        auto_import: bool = True,
        lang: str = "ch",
        use_angle_cls: bool = True,
    ) -> None:
        if ocr_engine is None:
            if not auto_import:
                raise ProviderDependencyError("paddleocr is required but not provided")
            try:
                from paddleocr import PaddleOCR  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise ProviderDependencyError(f"failed to import paddleocr: {exc}") from exc
            try:
                ocr_engine = PaddleOCR(lang=lang, use_angle_cls=use_angle_cls)
            except Exception as exc:  # pragma: no cover
                raise ProviderDependencyError(f"failed to init PaddleOCR: {exc}") from exc

        self._ocr = ocr_engine

    def extract_text(self, image_path: str | Path) -> list[dict[str, Any]]:
        p = Path(image_path)
        try:
            # PaddleOCR 2.x commonly supports `cls=...` per-call; PaddleOCR 3.x
            # may reject it (it can be controlled by `use_angle_cls` at init).
            try:
                raw = self._ocr.ocr(str(p), cls=True)
            except TypeError as exc:
                if "unexpected keyword argument" in str(exc) and "cls" in str(exc):
                    raw = self._ocr.ocr(str(p))
                else:
                    raise
            except Exception as exc:
                # Some versions raise from deeper layers (e.g. `predict(cls=...)`).
                if "unexpected keyword argument" in str(exc) and "cls" in str(exc):
                    raw = self._ocr.ocr(str(p))
                else:
                    raise
            return self._normalize(raw)
        except Exception as exc:
            raise ProviderActionError("ocr_extract", str(exc)) from exc

    def _normalize(self, raw: Any) -> list[dict[str, Any]]:
        if raw is None:
            return []
        lines = raw
        if isinstance(raw, (list, tuple)) and len(raw) == 1 and isinstance(raw[0], (list, tuple)):
            lines = raw[0]
        if not isinstance(lines, (list, tuple)):
            return []

        items: list[dict[str, Any]] = []
        for entry in lines:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            polygon = entry[0]
            payload = entry[1]
            text: str | None = None
            confidence: float | None = None
            if isinstance(payload, (list, tuple)) and len(payload) >= 1:
                text = str(payload[0])
                if len(payload) >= 2:
                    try:
                        confidence = float(payload[1])
                    except Exception:
                        confidence = None
            bbox = _bbox_from_polygon(polygon)
            out: dict[str, Any] = {"text": text, "confidence": confidence}
            if bbox is not None:
                out["bbox"] = bbox
            if isinstance(polygon, (list, tuple)):
                out["polygon"] = polygon
            items.append(out)
        return items


__all__ = ["PaddleOCRProvider", "ProviderActionError", "ProviderDependencyError"]
