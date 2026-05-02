"""Failure recovery driven by knowledge-base action sequences."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import config
from ..knowledge_base import AppKnowledge
from .operator import execute
from .parser import _parse_atomic_action
from .window_manager import (
    focus_target_app,
    is_target_app_in_foreground,
    launch_target_app,
)


@dataclass
class RecoveryResult:
    """恢复操作的结果描述。"""
    attempted: bool
    recovered: bool
    reason: str
    target_state: str = "unknown"


def ensure_target_app_focused(knowledge: AppKnowledge) -> RecoveryResult:
    """确保目标应用窗口在前台：已在前台→尝试聚焦→尝试启动。"""
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


def _execute_scripted_actions(actions: list[dict], screen_width: int = 4000, screen_height: int = 4000) -> None:
    """执行知识库中预定义的动作序列（不做坐标裁剪，使用大画布默认值）。"""
    for item in actions:
        action = _parse_atomic_action(
            item.get("action", ""),
            item.get("params", {}),
            screen_width,
            screen_height,
        )
        execute(action)


def navigate_to_state(target_state: str, knowledge: AppKnowledge) -> RecoveryResult:
    """通过知识库中的快捷键或恢复脚本导航到指定页面状态。

    优先使用 recovery_sequences.state_entry 中的脚本动作，
    其次回退到 state_navigation_hotkeys 中的快捷键。
    """
    state_entry = knowledge.recovery_sequences.get("state_entry", {})
    actions = state_entry.get(target_state, [])
    if not actions:
        hotkeys = knowledge.state_navigation_hotkeys.get(target_state)
        if hotkeys:
            actions = [{"action": "hotkey", "params": {"keys": hotkeys}}]
    if not actions:
        return RecoveryResult(
            attempted=True,
            recovered=False,
            reason=f"未配置页面状态 {target_state} 的恢复入口动作",
            target_state=target_state,
        )
    _execute_scripted_actions(actions)
    return RecoveryResult(
        attempted=True,
        recovered=True,
        reason=f"已执行状态入口动作并尝试到达 {target_state}",
        target_state=target_state,
    )


def recover_to_known_state(
    reason: str,
    knowledge: AppKnowledge,
    current_state: str = "unknown",
) -> RecoveryResult:
    """执行完整恢复流程：聚焦应用→全局恢复动作→导航到稳定主页状态。

    用于在验证失败或异常时恢复到已知可用状态。
    """
    focus_result = ensure_target_app_focused(knowledge)
    if not focus_result.recovered:
        return focus_result

    global_actions = knowledge.recovery_sequences.get("global", [])
    if global_actions:
        _execute_scripted_actions(global_actions)

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
