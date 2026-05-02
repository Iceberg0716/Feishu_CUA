"""Minimal MiMo text request based on the vendor sample."""

from __future__ import annotations

import json
import os

import httpx


def main() -> int:
    api_key = os.environ.get("CUA_API_KEY", "")
    base_url = os.environ.get("CUA_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")
    model = os.environ.get("CUA_MODEL", "mimo-v2.5-pro")
    if not api_key:
        raise RuntimeError("Missing CUA_API_KEY")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are MiMo, an AI assistant developed by Xiaomi. Today is date: Tuesday, December 16, 2025. Your knowledge cutoff date is December 2024.",
            },
            {
                "role": "user",
                "content": "please introduce yourself",
            },
        ],
        "max_completion_tokens": 1024,
    }
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        print("STATUS", response.status_code)
        print(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
