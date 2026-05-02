"""Configuration via environment variables and dataclass defaults."""

import os
from pathlib import Path
from dataclasses import dataclass, field


def _load_dotenv() -> None:
    """从项目根目录的 .env 文件加载环境变量（如文件不存在则跳过）。

    已存在的环境变量不会被覆盖（使用 setdefault）。
    支持注释行（以 # 开头）和带引号的值。
    """
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _select_api_key() -> str:
    """根据 base_url 自动选择对应的 API Key 环境变量。

    优先级:
      dashscope/aliyuncs → QWEN_API_KEY > DASHSCOPE_API_KEY > CUA_API_KEY
      minimaxi/mimo       → MIMO_API_KEY > CUA_API_KEY
      其他               → CUA_API_KEY > DASHSCOPE_API_KEY > OPENAI_API_KEY
    """
    base_url = os.environ.get(
        "CUA_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).lower()
    if "dashscope" in base_url or "aliyuncs" in base_url:
        return (
            os.environ.get("QWEN_API_KEY")
            or os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("CUA_API_KEY", "")
        )
    if "minimaxi" in base_url or "mimo" in base_url:
        return (
            os.environ.get("MIMO_API_KEY")
            or os.environ.get("CUA_API_KEY", "")
        )
    return (
        os.environ.get("CUA_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("OPENAI_API_KEY", "")
    )


@dataclass
class Config:
    """全局配置单例，所有值优先从环境变量读取，回退到类默认值。

    可通过 CUA_BASE_URL / CUA_MODEL / CUA_API_KEY 等环境变量覆盖。
    """
    dashscope_api_key: str = field(
        default_factory=_select_api_key
    )
    model_name: str = field(
        default_factory=lambda: os.environ.get("CUA_MODEL", "qwen-vl-max")
    )
    base_url: str = field(
        default_factory=lambda: os.environ.get(
            "CUA_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    )
    max_retries: int = 3                # VLM API 请求最大重试次数
    request_timeout: int = 30           # VLM API 请求超时秒数
    log_dir: str = "logs"              # 日志存储目录
    screenshot_dir: str = "logs/screenshots"  # 截图存储目录
    trace_file: str = "logs/trace.jsonl"     # 操作轨迹 JSONL 文件
    screenshot_prefix: str = "step_"    # 截图文件名前缀
    action_delay_min: float = 0.3       # 操作前随机延迟最小值(秒)
    action_delay_max: float = 0.8       # 操作前随机延迟最大值(秒)
    input_idle_timeout_s: float = 1.0   # 用户操作空闲判定超时(秒)
    input_poll_interval_s: float = 0.05 # 用户输入轮询间隔(秒)
    post_action_settle_timeout_s: float = 2.0   # 操作后界面稳定等待超时(秒)
    post_action_settle_poll_s: float = 0.2      # 操作后界面稳定轮询间隔(秒)
    screenshot_keep_failed: bool = True          # 是否保留失败步骤的截图
    screenshot_keep_passed: bool = False         # 是否保留通过步骤的截图
    screenshot_keep_latest_sessions: int = 3     # 保留最近 N 个会话目录
    screenshot_keep_max_age_hours: int = 24      # 截图最大保留时长(小时)
    recovery_max_attempts: int = 2               # 步骤级别最大重试次数
    app_knowledge_path: str = "knowledge/feishu.json"  # 应用知识库 JSON 路径
    app_launch_wait_s: float = 3.0               # 应用启动后等待时间(秒)
    localization_mode: str = "full_window"       # VLM 定位模式: "full_window"(全屏) / "region"(分区域)
    preclick_confirmation: bool = True           # 点击前是否做目标确认补丁（裁剪目标点附近区域让 VLM 确认）


config = Config()
