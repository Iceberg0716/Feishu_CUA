"""Configuration via environment variables and dataclass defaults."""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    dashscope_api_key: str = field(
        default_factory=lambda: os.environ.get(
            "DASHSCOPE_API_KEY",
            "sk-600f2af2fc024f2bbfd7392a7cc16368",
        )
    )
    model_name: str = field(
        default_factory=lambda: os.environ.get("CUA_MODEL", "qwen-vl-max")
    )
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    max_retries: int = 3
    request_timeout: int = 30
    log_dir: str = "logs"
    screenshot_dir: str = "logs/screenshots"
    trace_file: str = "logs/trace.jsonl"
    screenshot_prefix: str = "step_"
    action_delay_min: float = 0.3
    action_delay_max: float = 0.8


config = Config()
