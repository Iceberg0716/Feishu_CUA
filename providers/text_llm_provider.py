from __future__ import annotations

from typing import Any

import requests

from providers.errors import ProviderActionError, ProviderDependencyError


def _join_url(base_url: str, suffix: str) -> str:
    return base_url.rstrip("/") + "/" + suffix.lstrip("/")


class OpenAICompatibleTextLLMProvider:
    """
    OpenAI-compatible text-only chat provider.
    Used by `python main.py -i "<instruction>"` natural language planner.
    """

    def __init__(self, *, base_url: str, api_key: str | None, model: str, session: Any | None = None) -> None:
        if not api_key:
            raise ProviderDependencyError("llm api_key is required")
        if not base_url:
            raise ProviderDependencyError("llm base_url is required")
        if not model:
            raise ProviderDependencyError("llm model is required")
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._session = session or requests.Session()

    def chat_json(self, *, system_prompt: str, user_prompt: str, timeout_seconds: int = 30) -> str:
        try:
            payload = {
                "model": self._model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            url = _join_url(self._base_url, "/chat/completions")
            headers = {"Authorization": f"Bearer {self._api_key}"}
            resp = self._session.post(url, headers=headers, json=payload, timeout=int(timeout_seconds))
            if getattr(resp, "status_code", 500) >= 400:
                raise ProviderActionError("llm_chat_json", f"http {resp.status_code}: {getattr(resp, 'text', '')}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except ProviderActionError:
            raise
        except Exception as exc:
            raise ProviderActionError("llm_chat_json", str(exc)) from exc


__all__ = ["OpenAICompatibleTextLLMProvider", "ProviderActionError", "ProviderDependencyError"]

