"""Windows input activity guard for GUI automation."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes


user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

# 监控的虚拟键码范围：鼠标、Tab/Enter、修饰键、Esc、空格、方向键、数字键、字母键、功能键
VK_CODES = [
    0x01,  # left mouse
    0x02,  # right mouse
    0x04,  # middle mouse
    0x08,  # back mouse
    0x09,  # tab
    0x0D,  # enter
    0x10,  # shift
    0x11,  # ctrl
    0x12,  # alt
    0x1B,  # esc
    0x20,  # space
]
VK_CODES.extend(range(0x25, 0x29))  # arrows
VK_CODES.extend(range(0x30, 0x3A))  # digits
VK_CODES.extend(range(0x41, 0x5B))  # letters
VK_CODES.extend(range(0x70, 0x7C))  # F1-F12


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_cursor_pos() -> tuple[int, int]:
    """获取当前鼠标光标位置 (x, y)。"""
    if user32 is None:
        return 0, 0
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def has_keyboard_activity() -> bool:
    """检查当前是否有任何键盘按键处于按下状态。"""
    if user32 is None:
        return False
    for vk in VK_CODES:
        if user32.GetAsyncKeyState(vk) & 0x8000:
            return True
    return False


def wait_for_user_idle(idle_timeout_s: float, poll_interval_s: float) -> None:
    """Block until mouse and keyboard stay idle for the configured window."""
    last_pos = get_cursor_pos()
    stable_since = time.monotonic()

    while True:
        time.sleep(poll_interval_s)
        current_pos = get_cursor_pos()
        keyboard_active = has_keyboard_activity()
        mouse_moved = current_pos != last_pos
        if keyboard_active or mouse_moved:
            stable_since = time.monotonic()
            last_pos = current_pos
            continue
        if time.monotonic() - stable_since >= idle_timeout_s:
            return

