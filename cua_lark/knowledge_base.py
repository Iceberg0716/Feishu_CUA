"""Load external app knowledge from JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppKnowledge:
    app_names: tuple[str, ...]
    launch_commands: tuple[str, ...]
    known_page_states: tuple[str, ...]
    stable_home_state: str
    state_navigation_hotkeys: dict[str, list[str]]


def load_app_knowledge(path: str | Path) -> AppKnowledge:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AppKnowledge(
        app_names=tuple(data.get("app_names", [])),
        launch_commands=tuple(data.get("launch_commands", [])),
        known_page_states=tuple(data.get("known_page_states", [])),
        stable_home_state=data.get("stable_home_state", "unknown"),
        state_navigation_hotkeys=data.get("state_navigation_hotkeys", {}),
    )
