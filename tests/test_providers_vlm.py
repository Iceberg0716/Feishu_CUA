from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from providers.vlm_provider import ProviderActionError, ProviderDependencyError, VLMProvider


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class _DummySession:
    def __init__(self, response: _DummyResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, *, headers: dict, json: dict, timeout: int):  # noqa: ANN001
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.response


class TestVLMProvider(unittest.TestCase):
    def test_requires_api_key(self) -> None:
        with self.assertRaises(ProviderDependencyError):
            VLMProvider(base_url="https://example.com/v1", api_key=None, model="x", session=None)

    def test_judge_state_sends_openai_compatible_payload(self) -> None:
        content = {"success": True, "confidence": 0.9, "reason": "ok"}
        resp = _DummyResponse(
            200,
            {"choices": [{"message": {"content": json.dumps(content)}}]},
        )
        sess = _DummySession(resp)
        provider = VLMProvider(base_url="https://example.com/v1", api_key="k", model="m", session=sess)
        with tempfile.TemporaryDirectory() as td:
            img = Path(td) / "a.png"
            img.write_bytes(b"\x89PNG\r\n")
            out = provider.judge_state(img, expectation="see hello", timeout_seconds=12)
            self.assertTrue(out["success"])
            self.assertAlmostEqual(out["confidence"], 0.9, places=3)
            call = sess.calls[0]
            self.assertIn("/chat/completions", call["url"])
            self.assertEqual(call["json"]["model"], "m")
            # Ensure image is embedded as data URL
            msg = call["json"]["messages"][0]["content"]
            image_part = [p for p in msg if p.get("type") == "image_url"][0]
            url = image_part["image_url"]["url"]
            self.assertTrue(url.startswith("data:image/png;base64,"))
            base64.b64decode(url.split(",", 1)[1])

    def test_wraps_http_errors(self) -> None:
        resp = _DummyResponse(500, {"error": {"message": "boom"}})
        sess = _DummySession(resp)
        provider = VLMProvider(base_url="https://example.com/v1", api_key="k", model="m", session=sess)
        with tempfile.TemporaryDirectory() as td:
            img = Path(td) / "a.png"
            img.write_bytes(b"\x89PNG\r\n")
            with self.assertRaises(ProviderActionError):
                provider.judge_state(img, expectation="x")


if __name__ == "__main__":
    unittest.main()

