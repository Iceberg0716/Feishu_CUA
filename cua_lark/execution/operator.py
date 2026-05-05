"""GUI operation wrapper around PyAutoGUI."""

import random
import time

import pyautogui
import pyperclip

from ..config import config
from .action_types import (
    ActionChunk,
    ClickAction,
    DoubleClickAction,
    DragAction,
    HotkeyAction,
    MouseMoveAction,
    ScrollAction,
    TypeAction,
    WaitAction,
)

pyautogui.FAILSAFE = True  # 鼠标移至屏幕角落时自动触发异常，防止失控


def _human_delay(min_s: float = 0.3, max_s: float = 0.8):
    """随机延迟以模拟人类操作节奏，避免被反自动化检测。"""
    time.sleep(random.uniform(min_s, max_s))


def execute_click(action: ClickAction):
    _human_delay(config.action_delay_min, config.action_delay_max)
    pyautogui.click(x=action.x, y=action.y, button=action.button)


def execute_double_click(action: DoubleClickAction):
    _human_delay(config.action_delay_min, config.action_delay_max)
    pyautogui.doubleClick(x=action.x, y=action.y)


def execute_type(action: TypeAction):
    """模拟键盘输入。纯 ASCII 用 typewrite；含中文等非 ASCII 字符通过剪贴板 Ctrl+V 粘贴。

    粘贴前会清空目标输入框已有内容（Ctrl+A → Backspace），避免残留字符混入。
    """
    _human_delay(config.action_delay_min, config.action_delay_max)
    text = action.text
    # 纯 ASCII 文本直接模拟键盘输入
    if all(ord(c) < 128 for c in text):
        pyautogui.typewrite(text, interval=random.uniform(0.02, 0.06))
        return
    # 含非 ASCII 字符（如中文）：清空目标框 → 复制 → 粘贴
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.03)
    pyautogui.press("backspace")
    time.sleep(0.03)
    pyperclip.copy(text)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.05)


def execute_hotkey(action: HotkeyAction):
    _human_delay(config.action_delay_min, config.action_delay_max)
    pyautogui.hotkey(*action.keys)


def execute_scroll(action: ScrollAction):
    """执行滚轮操作，可选先定位光标到指定坐标再滚动。"""
    _human_delay(config.action_delay_min, config.action_delay_max)
    if action.x or action.y:
        pyautogui.moveTo(x=action.x, y=action.y, duration=0.05)
    pyautogui.scroll(action.dy)


def execute_wait(action: WaitAction):
    time.sleep(max(0, action.ms) / 1000.0)


def execute_mouse_move(action: MouseMoveAction):
    _human_delay(config.action_delay_min, config.action_delay_max)
    pyautogui.moveTo(x=action.x, y=action.y, duration=max(0.0, action.duration_s))


def execute_drag(action: DragAction):
    _human_delay(config.action_delay_min, config.action_delay_max)
    pyautogui.moveTo(x=action.start_x, y=action.start_y, duration=0.15)
    pyautogui.dragTo(
        x=action.end_x,
        y=action.end_y,
        duration=max(0.0, action.duration_s),
        button=action.button,
    )


def execute(action) -> None:
    """通用动作分发执行入口，递归处理 ActionChunk 中的子动作。"""
    if isinstance(action, ActionChunk):
        for sub_action in action.actions:
            execute(sub_action)
        return

    dispatch = {
        ClickAction: execute_click,
        DoubleClickAction: execute_double_click,
        TypeAction: execute_type,
        HotkeyAction: execute_hotkey,
        ScrollAction: execute_scroll,
        WaitAction: execute_wait,
        MouseMoveAction: execute_mouse_move,
        DragAction: execute_drag,
    }
    handler = dispatch.get(type(action))
    if handler is None:
        raise ValueError(f"Unknown action type: {type(action)}")
    handler(action)
