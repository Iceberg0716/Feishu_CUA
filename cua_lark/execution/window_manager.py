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
    """Windows 窗口基本信息。"""
    hwnd: int
    title: str
    is_foreground: bool


@dataclass
class WindowBounds:
    """窗口矩形边界，附带宽高属性。"""
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


def _get_window_text(hwnd: int) -> str:
    """通过 Win32 API 获取窗口标题文本。"""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def get_foreground_window() -> WindowInfo:
    """获取当前前台窗口信息。"""
    hwnd = user32.GetForegroundWindow()
    return WindowInfo(
        hwnd=hwnd,
        title=_get_window_text(hwnd),
        is_foreground=True,
    )


def get_foreground_window_bounds() -> WindowBounds | None:
    """获取前台窗口的屏幕坐标边界，失败或无效返回 None。"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    rect = wintypes.RECT()
    ok = user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if not ok:
        return None
    bounds = WindowBounds(rect.left, rect.top, rect.right, rect.bottom)
    if bounds.width <= 0 or bounds.height <= 0:
        return None
    return bounds


def list_visible_windows() -> list[WindowInfo]:
    """枚举所有可见窗口并标记哪个是当前前台窗口。"""
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
    """检查前台窗口标题是否包含目标应用名称。"""
    title = get_foreground_window().title.lower()
    return any(name.lower() in title for name in target_names)


def focus_target_app(target_names: tuple[str, ...]) -> WindowInfo | None:
    """在所有可见窗口中查找目标应用并将焦点切换到该窗口。"""
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
    """尝试通过 os.startfile 依次执行启动命令来启动目标应用。"""
    for command in launch_commands:
        try:
            os.startfile(command)
            time.sleep(wait_s)
            return True
        except OSError:
            continue
    return False
