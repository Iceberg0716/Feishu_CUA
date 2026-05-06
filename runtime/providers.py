from __future__ import annotations

from typing import Any

from providers import PaddleOCRProvider, PyAutoGUIProvider, PywinautoProvider, VLMProvider
from providers.errors import ProviderDependencyError


def build_providers(config: dict[str, Any]) -> dict[str, Any]:
    providers: dict[str, Any] = {}

    # GUI providers are baseline for MVP.
    providers["pyautogui"] = PyAutoGUIProvider()
    providers["pywinauto"] = PywinautoProvider()

    ocr_cfg = config.get("ocr") if isinstance(config.get("ocr"), dict) else {}
    ocr_enabled = bool(ocr_cfg.get("enabled", True))
    ocr_provider = str(ocr_cfg.get("provider") or "paddleocr").lower()
    if ocr_enabled and ocr_provider not in {"none", "disabled"}:
        if ocr_provider == "paddleocr":
            try:
                providers["ocr"] = PaddleOCRProvider(lang=str(ocr_cfg.get("language") or "ch"))
            except ProviderDependencyError:
                # Allow running without OCR if VLM is enabled and tools can fall back.
                if bool((config.get("vlm") or {}).get("enabled")):
                    pass
                else:
                    raise
        else:
            raise ProviderDependencyError(f"unsupported ocr provider: {ocr_provider}")

    vlm_cfg = config.get("vlm") if isinstance(config.get("vlm"), dict) else {}
    if bool(vlm_cfg.get("enabled")):
        base_url = str(vlm_cfg.get("base_url") or "")
        api_key = str(vlm_cfg.get("api_key") or "")
        model = str(vlm_cfg.get("model") or "")
        missing: list[str] = []
        if not base_url:
            missing.append("base_url")
        if not model:
            missing.append("model")
        if not api_key:
            missing.append("api_key")
        if missing:
            raise ProviderDependencyError(
                "vlm is enabled but missing "
                + ", ".join(missing)
                + " (check `.env` / env vars and `config.yaml` -> `vlm.*`)"
            )
        providers["vlm"] = VLMProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
        )

    return providers


__all__ = ["build_providers"]
