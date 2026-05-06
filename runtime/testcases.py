from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_testcase(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid testcase yaml: {p}")
    return data


__all__ = ["load_testcase"]

