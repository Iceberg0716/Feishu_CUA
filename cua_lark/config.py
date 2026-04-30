"""Configuration via environment variables and dataclass defaults."""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    dashscope_api_key: str = field(
        default_factory=lambda: os.environ.get(
            "DASHSCOPE_API_KEY",
            "sk-217aead60a6a414e95721a145195d6af",
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
    input_idle_timeout_s: float = 1.0
    input_poll_interval_s: float = 0.05
    post_action_settle_timeout_s: float = 2.0
    post_action_settle_poll_s: float = 0.2
    screenshot_keep_failed: bool = True
    screenshot_keep_passed: bool = False
    screenshot_keep_latest_sessions: int = 3
    screenshot_keep_max_age_hours: int = 24
    recovery_max_attempts: int = 2
    app_knowledge_path: str = "knowledge/feishu.json"
    app_launch_wait_s: float = 3.0


config = Config()
