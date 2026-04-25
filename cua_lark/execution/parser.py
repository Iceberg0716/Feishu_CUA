"""Parse VLM responses into typed Action objects."""

import json
import re

from .action_types import (
    Action,
    ClickAction,
    DoubleClickAction,
    HotkeyAction,
    ScrollAction,
    TypeAction,
)


def _extract_json(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks."""
    text = text.strip()

    # Try to extract from markdown code block
    if "```" in text:
        pattern = r"```(?:json)?\s*\n?(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

    # Try to find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]

    return text


def parse_action(vlm_response: str, screen_width: int, screen_height: int) -> Action:
    """Parse VLM response text into an Action object."""
    json_str = _extract_json(vlm_response)
    data = json.loads(json_str)

    action_type = data.get("action", "")
    params = data.get("params", {})

    if action_type == "click":
        x = max(0, min(int(params.get("x", 0)), screen_width))
        y = max(0, min(int(params.get("y", 0)), screen_height))
        return ClickAction(x=x, y=y)

    elif action_type == "double_click":
        x = max(0, min(int(params.get("x", 0)), screen_width))
        y = max(0, min(int(params.get("y", 0)), screen_height))
        return DoubleClickAction(x=x, y=y)

    elif action_type == "type":
        return TypeAction(text=params.get("text", ""))

    elif action_type == "hotkey":
        keys = params.get("keys", [])
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split("+")]
        return HotkeyAction(keys=keys)

    elif action_type == "scroll":
        return ScrollAction(dy=int(params.get("dy", 0)))

    else:
        raise ValueError(f"Unknown action type: {action_type}")
