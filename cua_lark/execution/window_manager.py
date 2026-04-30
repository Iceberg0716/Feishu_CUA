"""Windows foreground window inspection and activation helpers."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass


user32 = ctypes.windll.user32


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    is_foreground: bool


def _get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def get_foreground_window() -> WindowInfo:
    hwnd = user32.GetForegroundWindow()
    return WindowInfo(
        hwnd=hwnd,
        title=_get_window_text(hwnd),
        is_foreground=True,
    )


def list_visible_windows() -> list[WindowInfo]:
    windows: list[WindowInfo] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd: int, lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _get_window_text(hwnd)
        if not title.strip():
            return True
        windows.append(
            WindowInfo(
                hwnd=hwnd,
                title=title,
                is_foreground=False,
            )
        )
        return True

    user32.EnumWindows(enum_proc, 0)
    foreground = user32.GetForegroundWindow()
    for window in windows:
        if window.hwnd == foreground:
            window.is_foreground = True
    return windows


def is_target_app_in_foreground(target_names: tuple[str, ...]) -> bool:
    title = get_foreground_window().title.lower()
    return any(name.lower() in title for name in target_names)


def focus_target_app(target_names: tuple[str, ...]) -> WindowInfo | None:
    for window in list_visible_windows():
        title = window.title.lower()
        if not any(name.lower() in title for name in target_names):
            continue
        user32.ShowWindow(window.hwnd, 5)
        user32.SetForegroundWindow(window.hwnd)
        return WindowInfo(
            hwnd=window.hwnd,
            title=window.title,
            is_foreground=True,
        )
    return None


def launch_target_app(launch_commands: tuple[str, ...], wait_s: float) -> bool:
    for command in launch_commands:
        try:
            os.startfile(command)
            time.sleep(wait_s)
            return True
        except OSError:
            continue
    return False
