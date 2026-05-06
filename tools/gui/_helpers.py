from __future__ import annotations

from typing import Any

from runtime.context import RunContext


def get_provider(context: RunContext, key: str) -> Any:
    providers = context.metadata.get("providers")
    if not isinstance(providers, dict) or key not in providers:
        raise KeyError(f"provider not configured: {key}")
    return providers[key]

