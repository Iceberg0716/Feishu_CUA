from __future__ import annotations

import base64

import tempfile
from pathlib import Path
from typing import Any

from providers.errors import ProviderActionError
from providers.vlm_provider import VLMProvider


# A valid 64x64 PNG (base64-decoded). Some VLM endpoints enforce minimum
# dimensions (e.g. height/width > 10), so 1x1 will fail.
_PING_PNG_B64 = (
    b"iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAfElEQVR4nNXOQREAIADDsFL/nocIHlyjIGcbZRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncf4OvLpyqgN9ZSiDcwAAAABJRU5ErkJggg=="
)


def check_vlm_connectivity(
    *,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    timeout_seconds: int = 8,
    session: Any | None = None,
) -> dict[str, Any]:
    """
    Best-effort connectivity check for OpenAI-compatible VLM endpoints.
    Returns dict with:
      - ok: bool
      - error: str | None
    """
    if not base_url or not model or not api_key:
        return {"ok": False, "error": "missing base_url/model/api_key"}

    try:
        with tempfile.TemporaryDirectory() as td:
            img = Path(td) / "ping.png"
            img.write_bytes(base64.b64decode(_PING_PNG_B64))
            prov = VLMProvider(base_url=base_url, api_key=api_key, model=model, session=session)
            prov.judge_state(img, expectation="ping", timeout_seconds=timeout_seconds)
        return {"ok": True, "error": None}
    except ProviderActionError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": str(exc)}


__all__ = ["check_vlm_connectivity"]
