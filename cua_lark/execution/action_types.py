"""Action type definitions for agent operations.

定义8种原子操作 (Click, DoubleClick, Type, Hotkey, Scroll, Wait, MouseMove, Drag)
以及动作块 ActionChunk 用于组合多个原子操作。
"""

from dataclasses import dataclass, field
from typing import Union


@dataclass
class ClickAction:
    """鼠标单击操作。"""
    x: int
    y: int
    button: str = "left"


@dataclass
class DoubleClickAction:
    """鼠标双击操作。"""
    x: int
    y: int


@dataclass
class TypeAction:
    """键盘输入操作。"""
    text: str


@dataclass
class HotkeyAction:
    """组合热键操作，如 ['ctrl', 'f']。"""
    keys: list[str]


@dataclass
class ScrollAction:
    """鼠标滚轮操作，dy 正数为上滚。可选 x/y 指定滚轮前光标定位点（0 表示不移动）。"""
    dy: int
    x: int = 0
    y: int = 0


@dataclass
class WaitAction:
    """等待操作（毫秒）。"""
    ms: int


@dataclass
class MouseMoveAction:
    """鼠标移动操作，带过渡时长。"""
    x: int
    y: int
    duration_s: float = 0.2


@dataclass
class DragAction:
    """鼠标拖拽操作，从起点拖到终点。"""
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    duration_s: float = 0.4
    button: str = "left"


# 所有原子操作的联合类型
AtomicAction = Union[
    ClickAction,
    DoubleClickAction,
    TypeAction,
    HotkeyAction,
    ScrollAction,
    WaitAction,
    MouseMoveAction,
    DragAction,
]


@dataclass
class ActionChunk:
    """动作块：包含一组原子操作，支持逐步验证和失败停止。"""
    goal: str = ""
    actions: list[AtomicAction] = field(default_factory=list)
    verify_each_step: bool = False   # 是否在每步后验证
    stop_on_failure: bool = True     # 某步失败是否停止后续步骤


Action = Union[AtomicAction, ActionChunk]
