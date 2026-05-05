"""Parse VLM responses into typed Action objects."""

import json
import re

from .action_types import (
    Action,
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


def _extract_json(text: str) -> str:
    """从 VLM 响应文本中提取 JSON 字符串。

    支持三种格式：markdown代码块（```json...```）、裸 JSON 对象（{}包裹）、纯文本。
    """
    text = text.strip()
    if "```" in text:
        pattern = r"```(?:json)?\s*\n?(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _clamp(value: int, limit: int) -> int:
    """将坐标值限制在 [0, limit] 范围内，防止越界。"""
    return max(0, min(value, limit))


def _parse_atomic_action(action_type: str, params: dict, screen_width: int, screen_height: int):
    """将单个动作字典解析为对应的 Action 对象，自动对坐标进行边界裁剪。

    Args:
        action_type: 动作类型名 (click, double_click, type, hotkey, scroll, wait, mouse_move, drag)
        params: 动作参数字典
        screen_width: 屏幕宽（用于坐标裁剪上限）
        screen_height: 屏幕高（用于坐标裁剪上限）
    """
    if action_type == "click":
        return ClickAction(
            x=_clamp(int(params.get("x", 0)), screen_width),
            y=_clamp(int(params.get("y", 0)), screen_height),
            button=params.get("button", "left"),
        )
    if action_type == "double_click":
        return DoubleClickAction(
            x=_clamp(int(params.get("x", 0)), screen_width),
            y=_clamp(int(params.get("y", 0)), screen_height),
        )
    if action_type == "type":
        return TypeAction(text=params.get("text", ""))
    if action_type == "hotkey":
        keys = params.get("keys", [])
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split("+")]
        return HotkeyAction(keys=keys)
    if action_type == "scroll":
        # 兼容多种 VLM 输出格式: dy（像素量）, pixels, amount, direction；可选 x/y 定位光标
        dy = params.get("dy")
        if dy is None:
            dy = params.get("pixels")
        if dy is None:
            dy = params.get("amount")
        if dy is None:
            direction = params.get("direction", "")
            dy = 300 if direction == "up" else (-300 if direction == "down" else 0)
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        return ScrollAction(dy=int(dy), x=x, y=y)
    if action_type == "wait":
        return WaitAction(ms=int(params.get("ms", 500)))
    if action_type == "mouse_move":
        return MouseMoveAction(
            x=_clamp(int(params.get("x", 0)), screen_width),
            y=_clamp(int(params.get("y", 0)), screen_height),
            duration_s=float(params.get("duration_s", 0.2)),
        )
    if action_type == "drag":
        return DragAction(
            start_x=_clamp(int(params.get("start_x", 0)), screen_width),
            start_y=_clamp(int(params.get("start_y", 0)), screen_height),
            end_x=_clamp(int(params.get("end_x", 0)), screen_width),
            end_y=_clamp(int(params.get("end_y", 0)), screen_height),
            duration_s=float(params.get("duration_s", 0.4)),
            button=params.get("button", "left"),
        )
    raise ValueError(f"Unknown action type: {action_type}")


def parse_action(vlm_response: str, screen_width: int, screen_height: int) -> Action:
    """解析 VLM 原始响应，自动识别单步动作或动作块并返回统一的 Action 对象。"""
    json_str = _extract_json(vlm_response)
    data = json.loads(json_str)

    if "actions" in data and isinstance(data["actions"], list):
        actions = []
        for item in data["actions"]:
            actions.append(
                _parse_atomic_action(
                    item.get("action", ""),
                    item.get("params", {}),
                    screen_width,
                    screen_height,
                )
            )
        return ActionChunk(
            goal=data.get("goal", ""),
            actions=actions,
            verify_each_step=bool(data.get("verify_each_step", False)),
            stop_on_failure=bool(data.get("stop_on_failure", True)),
        )

    return _parse_atomic_action(
        data.get("action", ""),
        data.get("params", {}),
        screen_width,
        screen_height,
    )
