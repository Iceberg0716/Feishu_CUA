from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from runtime.env import load_dotenv

_ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _expand_env_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    match = _ENV_PATTERN.match(value.strip())
    if not match:
        return value
    env_key = match.group(1)
    return os.environ.get(env_key)


def expand_env_vars(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env_vars(v) for v in obj]
    return _expand_env_scalar(obj)


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    # Allow manual env registration via `.env` without hardcoding secrets in YAML/code.
    # This is a best-effort optional load: missing `.env` is OK.
    load_dotenv(".env", override=False)
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return expand_env_vars(data)
