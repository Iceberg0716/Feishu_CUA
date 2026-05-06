from __future__ import annotations

import json
import unittest

from runtime.diagnostics import check_vlm_connectivity


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

    def post(self, url: str, *, headers: dict, json: dict, timeout: int):  # noqa: ANN001
        return self.response


class TestDiagnostics(unittest.TestCase):
    def test_missing_fields(self) -> None:
        out = check_vlm_connectivity(base_url=None, api_key="k", model="m")
        self.assertFalse(out["ok"])

    def test_ok_when_endpoint_returns_valid_json(self) -> None:
        resp = _DummyResponse(200, {"choices": [{"message": {"content": "{\"success\": true, \"confidence\": 0.9, \"reason\": \"ok\"}"}}]})
        out = check_vlm_connectivity(
            base_url="https://example.com/v1",
            api_key="k",
            model="m",
            session=_DummySession(resp),
            timeout_seconds=1,
        )
        self.assertTrue(out["ok"])

    def test_error_when_http_error(self) -> None:
        resp = _DummyResponse(401, {"error": {"message": "bad"}})
        out = check_vlm_connectivity(
            base_url="https://example.com/v1",
            api_key="k",
            model="m",
            session=_DummySession(resp),
            timeout_seconds=1,
        )
        self.assertFalse(out["ok"])
        self.assertIn("http 401", out["error"])


if __name__ == "__main__":
    unittest.main()

