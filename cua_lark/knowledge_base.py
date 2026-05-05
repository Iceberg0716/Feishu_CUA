"""Load external app knowledge from JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppKnowledge:
    """应用知识库，从 JSON 文件加载的不可变数据容器。

    包含应用名称、启动命令、页面状态定义、快捷键映射、
    区域搜索优先级、验证策略、恢复序列和任务模板。
    """
    app_names: tuple[str, ...]
    launch_commands: tuple[str, ...]
    known_page_states: tuple[str, ...]
    stable_home_state: str
    state_navigation_hotkeys: dict[str, list[str]]
    region_preferences: dict[str, list[str]]
    validation_policies: dict[str, dict[str, bool]]
    recovery_sequences: dict[str, object]
    task_templates: list[dict[str, object]]


def load_app_knowledge(path: str | Path) -> AppKnowledge:
    """从 JSON 文件加载应用知识库并返回不可变 AppKnowledge 实例。

    Args:
        path: JSON 知识库文件路径（如 knowledge/feishu.json）
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AppKnowledge(
        app_names=tuple(data.get("app_names", [])),
        launch_commands=tuple(data.get("launch_commands", [])),
        known_page_states=tuple(data.get("known_page_states", [])),
        stable_home_state=data.get("stable_home_state", "unknown"),
        state_navigation_hotkeys=data.get("state_navigation_hotkeys", {}),
        region_preferences=data.get("region_preferences", {}),
        validation_policies=data.get("validation_policies", {}),
        recovery_sequences=data.get("recovery_sequences", {}),
        task_templates=data.get("task_templates", []),
    )
