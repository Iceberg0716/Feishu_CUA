"""Foreground window inspection and activation helpers (Windows + macOS)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from dataclasses import dataclass

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

if IS_WIN:
    from ctypes import wintypes
    user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
else:
    wintypes = None  # type: ignore[assignment]
    user32 = None


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
    if user32 is None:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _mac_frontmost_app() -> str:
    """macOS: 通过 AppleScript 获取当前前台应用名称。"""
    try:
        out = subprocess.check_output(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            text=True, timeout=5,
        )
        return out.strip()
    except Exception:
        return ""


def _mac_visible_apps() -> list[str]:
    """macOS: 获取所有可见应用进程名称列表。"""
    try:
        out = subprocess.check_output(
            ["osascript", "-e",
             'tell application "System Events" to get name of every application process whose visible is true'],
            text=True, timeout=5,
        )
        return [n.strip() for n in out.strip().split(",") if n.strip()]
    except Exception:
        return []


def _mac_activate_app(app_name: str) -> bool:
    """macOS: 通过 AppleScript 激活指定应用并确保窗口可见（处理最小化等情况）。"""
    script = (
        f'tell application "{app_name}"\n'
        f'  reopen\n'
        f'  activate\n'
        f'end tell\n'
        f'delay 0.3\n'
        f'tell application "System Events"\n'
        f'  tell process "{app_name}"\n'
        f'    set frontmost to true\n'
        f'    if (count of windows) > 0 then\n'
        f'      perform action "AXRaise" of window 1\n'
        f'    end if\n'
        f'  end tell\n'
        f'end tell\n'
    )
    try:
        subprocess.check_call(
            ["osascript", "-e", script],
            timeout=8,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        return True
    except Exception:
        pass
    # 回退: 仅 activate
    try:
        subprocess.check_call(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            timeout=5,
        )
        time.sleep(0.5)
        return True
    except Exception:
        return False


def get_foreground_window() -> WindowInfo:
    """获取当前前台窗口信息。"""
    if IS_MAC:
        name = _mac_frontmost_app()
        return WindowInfo(hwnd=0, title=name, is_foreground=True)
    if user32 is None:
        return WindowInfo(hwnd=0, title="", is_foreground=True)
    hwnd = user32.GetForegroundWindow()
    return WindowInfo(
        hwnd=hwnd,
        title=_get_window_text(hwnd),
        is_foreground=True,
    )


def get_foreground_window_bounds() -> WindowBounds | None:
    """获取前台窗口的屏幕坐标边界，失败或无效返回 None。"""
    if IS_MAC:
        try:
            script = (
                'tell application "System Events"\n'
                '  set fp to first application process whose frontmost is true\n'
                '  tell fp\n'
                '    set w to first window\n'
                '    set {x, y} to position of w\n'
                '    set {sw, sh} to size of w\n'
                '    return (x as text) & "," & (y as text) & "," & ((x + sw) as text) & "," & ((y + sh) as text)\n'
                '  end tell\n'
                'end tell'
            )
            out = subprocess.check_output(
                ["osascript", "-e", script], text=True, timeout=5,
            ).strip()
            parts = [int(p) for p in out.split(",")]
            if len(parts) == 4:
                bounds = WindowBounds(*parts)
                if bounds.width > 0 and bounds.height > 0:
                    return bounds
        except Exception:
            pass
        return None
    if user32 is None:
        return None
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
    if IS_MAC:
        front = _mac_frontmost_app().lower()
        results: list[WindowInfo] = []
        for name in _mac_visible_apps():
            results.append(WindowInfo(
                hwnd=0,
                title=name,
                is_foreground=(name.lower() == front),
            ))
        return results
    if user32 is None:
        return []
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
    if IS_MAC:
        for window in list_visible_windows():
            title = window.title.lower()
            if not any(name.lower() in title for name in target_names):
                continue
            if _mac_activate_app(window.title):
                return WindowInfo(hwnd=0, title=window.title, is_foreground=True)
        return None
    if user32 is None:
        return None
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
    """尝试启动目标应用：macOS 用 open 命令，Windows 用 os.startfile。"""
    if IS_MAC:
        mac_apps = ("Feishu", "飞书", "Lark")
        for app_name in mac_apps:
            try:
                subprocess.check_call(
                    ["open", "-a", app_name],
                    timeout=10,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(wait_s)
                return True
            except Exception:
                continue
        for command in launch_commands:
            if command.endswith("://"):
                try:
                    subprocess.check_call(
                        ["open", command],
                        timeout=10,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    time.sleep(wait_s)
                    return True
                except Exception:
                    continue
        return False
    if not hasattr(os, "startfile"):
        return False
    for command in launch_commands:
        try:
            os.startfile(command)
            time.sleep(wait_s)
            return True
        except OSError:
            continue
    return False
