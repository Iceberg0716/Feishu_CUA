"""Failure recovery skeleton for desktop automation."""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..config import config
from ..knowledge_base import AppKnowledge
from .action_types import HotkeyAction
from .operator import execute
from .window_manager import (
    focus_target_app,
    is_target_app_in_foreground,
    launch_target_app,
)


@dataclass
class RecoveryResult:
    attempted: bool
    recovered: bool
    reason: str
    target_state: str = "unknown"


def ensure_target_app_focused(knowledge: AppKnowledge) -> RecoveryResult:
    if is_target_app_in_foreground(knowledge.app_names):
        return RecoveryResult(True, True, "目标应用已在前台")
    window = focus_target_app(knowledge.app_names)
    if window is not None:
        return RecoveryResult(True, True, f"已聚焦窗口: {window.title}")

    launched = launch_target_app(
        launch_commands=knowledge.launch_commands,
        wait_s=config.app_launch_wait_s,
    )
    if not launched:
        return RecoveryResult(True, False, "未找到目标应用窗口，且启动飞书失败")

    window = focus_target_app(knowledge.app_names)
    if window is None:
        return RecoveryResult(True, False, "已尝试启动飞书，但仍未找到目标应用窗口")
    return RecoveryResult(True, True, f"未检测到飞书，已启动并聚焦窗口: {window.title}")


def navigate_to_state(target_state: str, knowledge: AppKnowledge) -> RecoveryResult:
    hotkeys = knowledge.state_navigation_hotkeys.get(target_state)
    if not hotkeys:
        return RecoveryResult(
            attempted=True,
            recovered=False,
            reason=f"未配置页面状态 {target_state} 的导航快捷键",
            target_state=target_state,
        )
    execute(HotkeyAction(keys=hotkeys))
    time.sleep(0.5)
    return RecoveryResult(
        attempted=True,
        recovered=True,
        reason=f"已尝试导航到 {target_state}",
        target_state=target_state,
    )


def recover_to_known_state(
    reason: str,
    knowledge: AppKnowledge,
    current_state: str = "unknown",
) -> RecoveryResult:
    focus_result = ensure_target_app_focused(knowledge)
    if not focus_result.recovered:
        return focus_result

    execute(HotkeyAction(keys=["esc"]))
    home_state = knowledge.stable_home_state
    navigate_result = navigate_to_state(home_state, knowledge)
    if not navigate_result.recovered:
        return RecoveryResult(
            attempted=True,
            recovered=False,
            reason=f"恢复失败，无法导航到稳定模块: {navigate_result.reason}",
            target_state=home_state,
        )
    return RecoveryResult(
        attempted=True,
        recovered=True,
        reason=f"已从 {current_state} 恢复并导航到稳定模块 {home_state}: {reason}",
        target_state=home_state,
    )
