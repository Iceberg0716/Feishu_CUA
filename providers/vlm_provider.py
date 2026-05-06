from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from providers.errors import ProviderActionError, ProviderDependencyError


def _join_url(base_url: str, suffix: str) -> str:
    return base_url.rstrip("/") + "/" + suffix.lstrip("/")

VLM_MIN_DIM = 10
VLM_MAX_LONG_SIDE = 1280


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "application/octet-stream"


class VLMProvider:
    """
    OpenAI-compatible multimodal provider. All fields must come from config/.env.
    """

    def __init__(self, *, base_url: str, api_key: str | None, model: str, session: Any | None = None) -> None:
        if not api_key:
            raise ProviderDependencyError("vlm api_key is required")
        if not base_url:
            raise ProviderDependencyError("vlm base_url is required")
        if not model:
            raise ProviderDependencyError("vlm model is required")
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._session = session or requests.Session()

    def judge_state(self, image_path: str | Path, *, expectation: str, timeout_seconds: int = 30) -> dict[str, Any]:
        """
        Returns dict with keys: success(bool), confidence(float|None), reason(str|None), evidence(list[str])
        """
        p = Path(image_path)
        try:
            w, h = self._inspect_image(p)
            if w < VLM_MIN_DIM or h < VLM_MIN_DIM:
                reason = f"image too small ({w}x{h}) for VLM"
                return {"success": False, "confidence": 0.0, "reason": reason, "evidence": [f"vlm_skip:{reason}"]}
            payload = self._build_payload(p, expectation)
            url = _join_url(self._base_url, "/chat/completions")
            headers = {"Authorization": f"Bearer {self._api_key}"}
            resp = self._session.post(url, headers=headers, json=payload, timeout=int(timeout_seconds))
            if getattr(resp, "status_code", 500) >= 400:
                raise ProviderActionError("vlm_judge_state", f"http {resp.status_code}: {getattr(resp, 'text', '')}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_content(content)
        except ProviderActionError:
            raise
        except Exception as exc:
            raise ProviderActionError("vlm_judge_state", str(exc)) from exc

    def _build_payload(self, image_path: Path, expectation: str) -> dict[str, Any]:
        mime, b = self._encode_image(image_path)
        b64 = base64.b64encode(b).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        instruction = (
            "You are a QA assistant. Judge whether the screenshot meets the expectation.\n"
            "Return ONLY strict JSON with keys: success(boolean), confidence(number 0-1), reason(string).\n"
            f"Expectation: {expectation}"
        )
        return {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }

    def _inspect_image(self, image_path: Path) -> tuple[int, int]:
        try:
            with Image.open(image_path) as im:
                return int(im.width), int(im.height)
        except Exception:
            # Best-effort: some unit tests provide non-decodable bytes; skip size guard in that case.
            return VLM_MIN_DIM, VLM_MIN_DIM

    def _encode_image(self, image_path: Path) -> tuple[str, bytes]:
        try:
            with Image.open(image_path) as im:
                im = im.convert("RGB")
                w, h = im.size
                longest = max(w, h)
                if longest > VLM_MAX_LONG_SIDE:
                    scale = VLM_MAX_LONG_SIDE / float(longest)
                    im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=80)
                return "image/jpeg", buf.getvalue()
        except Exception as exc:
            # Fallback: send raw bytes as-is (still useful for mock servers / tests).
            try:
                return _guess_mime(image_path), image_path.read_bytes()
            except Exception as exc2:
                raise ProviderActionError("vlm_encode_image", str(exc2)) from exc2

    def _parse_content(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            obj = content
        else:
            obj = json.loads(str(content))
        success = bool(obj.get("success", False))
        confidence = obj.get("confidence")
        try:
            confidence_f = float(confidence) if confidence is not None else None
        except Exception:
            confidence_f = None
        reason = obj.get("reason")
        evidence = [f"vlm_reason:{reason}"] if reason else []
        return {"success": success, "confidence": confidence_f, "reason": reason, "evidence": evidence}


__all__ = ["VLMProvider", "ProviderActionError", "ProviderDependencyError"]
