"""Qwen-VL API client for screen analysis and verification.

Uses the OpenAI-compatible DashScope endpoint.
"""

import base64
import json
import io
import time
from dataclasses import dataclass

from openai import OpenAI
from PIL import Image

from ..config import config

SYSTEM_PROMPT = """你是一个GUI自动化操作助手。分析屏幕截图，根据用户指令定位目标元素，输出精确的操作指令。

输出格式要求（严格JSON，不要输出任何其他内容）：
{
  "thought": "分析当前界面状态和要执行的操作",
  "action": "click|double_click|type|hotkey|scroll",
  "params": {
    // click/double_click: "x": 整数屏幕像素横坐标, "y": 整数屏幕像素纵坐标
    // type: "text": "要输入的文本"
    // hotkey: "keys": ["ctrl", "v"]
    // scroll: "dy": 整数，正数上滚负数下滚
  },
  "confidence": 0.0到1.0
}

规则：
1. 坐标(0,0)是屏幕左上角，使用实际屏幕像素坐标
2. 先仔细观察界面，找到目标元素再输出坐标
3. 如果找不到目标元素，confidence设为0并在thought中说明
4. 只输出JSON，绝对不要输出markdown代码块或其他文字"""

VERIFY_PROMPT = """你是一个GUI测试验证助手。对比操作前后的两张截图，判断操作是否达到了预期效果。

输出格式要求（严格JSON）：
{
  "passed": true或false,
  "reason": "判断依据",
  "confidence": 0.0到1.0
}
只输出JSON，不要输出其他内容。"""


def _encode_image(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _build_client():
    return OpenAI(
        api_key=config.dashscope_api_key,
        base_url=config.base_url,
        timeout=config.request_timeout,
    )


@dataclass
class VlmActionResponse:
    thought: str
    action: str
    params: dict
    confidence: float
    raw_response: str


@dataclass
class VlmVerifyResponse:
    passed: bool
    reason: str
    confidence: float
    raw_response: str


def analyze_screen(image: Image.Image, instruction: str) -> VlmActionResponse:
    """Send screenshot + instruction to VLM, return structured action."""
    client = _build_client()
    image_b64 = _encode_image(image)

    for attempt in range(config.max_retries):
        try:
            response = client.chat.completions.create(
                model=config.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": [{"type": "text", "text": SYSTEM_PROMPT}],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}"
                                },
                            },
                            {"type": "text", "text": instruction},
                        ],
                    },
                ],
            )

            raw = response.choices[0].message.content
            parsed = json.loads(raw)
            return VlmActionResponse(
                thought=parsed.get("thought", ""),
                action=parsed.get("action", ""),
                params=parsed.get("params", {}),
                confidence=parsed.get("confidence", 0.0),
                raw_response=raw,
            )

        except json.JSONDecodeError:
            if attempt < config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise RuntimeError(f"VLM response was not valid JSON: {raw}")
        except Exception as e:
            if attempt < config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise


def verify_result(
    before: Image.Image, after: Image.Image, expected: str
) -> VlmVerifyResponse:
    """Compare before/after screenshots to verify action success."""
    client = _build_client()
    before_b64 = _encode_image(before)
    after_b64 = _encode_image(after)

    user_message = f"""操作前截图（第一张）和操作后截图（第二张）。
预期效果：{expected}
判断操作是否成功达到预期效果。"""

    for attempt in range(config.max_retries):
        try:
            response = client.chat.completions.create(
                model=config.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": [{"type": "text", "text": VERIFY_PROMPT}],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{before_b64}"
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{after_b64}"
                                },
                            },
                            {"type": "text", "text": user_message},
                        ],
                    },
                ],
            )

            raw = response.choices[0].message.content
            parsed = json.loads(raw)
            return VlmVerifyResponse(
                passed=parsed.get("passed", False),
                reason=parsed.get("reason", ""),
                confidence=parsed.get("confidence", 0.0),
                raw_response=raw,
            )

        except json.JSONDecodeError:
            if attempt < config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise RuntimeError(f"VLM verify response was not valid JSON: {raw}")
        except Exception as e:
            if attempt < config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise
