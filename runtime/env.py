from __future__ import annotations

import os
from pathlib import Path


def _strip_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1]
    return v


def load_dotenv(path: str | Path = ".env", *, override: bool = False) -> dict[str, str]:
    """
    Minimal .env loader:
    - supports KEY=VALUE lines (VALUE may be quoted)
    - ignores empty lines and lines starting with '#'
    - does not expand ${...} inside values
    Returns the variables loaded from the file.
    """
    p = Path(path)
    if not p.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = _strip_quotes(value)
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


__all__ = ["load_dotenv"]

