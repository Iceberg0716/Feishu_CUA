"""Trace recorder for action history."""

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .config import config
from .execution.action_types import Action


def _serialize_action(action: Action) -> dict:
    """将 Action 对象序列化为字典，附带类型标记 _type。"""
    result = asdict(action)
    result["_type"] = type(action).__name__
    return result


class Recorder:
    """轨迹记录器，将每一步操作的完整信息以 JSONL 格式追加写入。"""

    def __init__(self, trace_file: str | None = None):
        self.trace_file = trace_file or config.trace_file
        Path(os.path.dirname(self.trace_file)).mkdir(parents=True, exist_ok=True)

    def record(
        self,
        instruction: str,
        vlm_raw: str,
        action: Action,
        verdict_passed: bool,
        verdict_reason: str,
        before_path: str,
        after_path: str,
    ) -> None:
        """向 trace.jsonl 追加一条操作记录。"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "instruction": instruction,
            "vlm_response": vlm_raw,
            "action": _serialize_action(action),
            "verdict": {
                "passed": verdict_passed,
                "reason": verdict_reason,
            },
            "screenshots": {
                "before": before_path,
                "after": after_path,
            },
        }
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
