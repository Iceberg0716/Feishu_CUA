"""Trace recorder for action history — foundation for record-replay."""

import json
import os
from datetime import datetime
from dataclasses import asdict
from pathlib import Path

from .execution.action_types import Action


def _serialize_action(action: Action) -> dict:
    result = asdict(action)
    result["_type"] = type(action).__name__
    return result


class Recorder:
    def __init__(self, trace_file: str = "logs/trace.jsonl"):
        Path(os.path.dirname(trace_file)).mkdir(parents=True, exist_ok=True)
        self.trace_file = trace_file

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
