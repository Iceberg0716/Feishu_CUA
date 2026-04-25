"""GUI operation wrapper around PyAutoGUI."""

import random
import time
import pyautogui

from .action_types import (
    ClickAction,
    DoubleClickAction,
    HotkeyAction,
    ScrollAction,
    TypeAction,
)

# Safety: pyautogui fail-safe - moving to corner (0,0) aborts
pyautogui.FAILSAFE = True


def _human_delay(min_s: float = 0.3, max_s: float = 0.8):
    time.sleep(random.uniform(min_s, max_s))


def execute_click(action: ClickAction):
    _human_delay()
    pyautogui.click(x=action.x, y=action.y, button=action.button)


def execute_double_click(action: DoubleClickAction):
    _human_delay()
    pyautogui.doubleClick(x=action.x, y=action.y)


def execute_type(action: TypeAction):
    _human_delay()
    pyautogui.typewrite(action.text, interval=random.uniform(0.02, 0.06))


def execute_hotkey(action: HotkeyAction):
    _human_delay()
    pyautogui.hotkey(*action.keys)


def execute_scroll(action: ScrollAction):
    _human_delay()
    pyautogui.scroll(action.dy)


def execute(action) -> None:
    """Dispatch action to the correct handler."""
    dispatch = {
        ClickAction: execute_click,
        DoubleClickAction: execute_double_click,
        TypeAction: execute_type,
        HotkeyAction: execute_hotkey,
        ScrollAction: execute_scroll,
    }
    handler = dispatch.get(type(action))
    if handler is None:
        raise ValueError(f"Unknown action type: {type(action)}")
    handler(action)
