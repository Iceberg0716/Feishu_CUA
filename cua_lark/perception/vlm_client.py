"""Qwen-VL API client for screen analysis and verification.

Uses the OpenAI-compatible DashScope endpoint.
"""

import base64
import json
import io
import time
from dataclasses import dataclass

import re

from openai import OpenAI
from PIL import Image

from ..config import config


def _extract_json(text: str) -> str:
    """Extract JSON string from VLM response, handling markdown code blocks."""
    text = text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text

SYSTEM_PROMPT = """你是一个GUI自动化操作助手。根据屏幕截图和用户指令精确找到目标元素，输出操作指令。

当用户指令涉及飞书左侧导航栏图标时，你必须先用肉眼从上到下逐一扫描侧边栏的每一个图标，列出你真实看到的图标和它的大致Y坐标位置。不要背飞书的图标固定顺序，每张截图都重新看。

飞书侧边栏图标仅供参考（以截图实际内容为准）：
- 消息：聊天气泡图标
- 日历：日历本图标，可能有数字
- 云文档：文档/纸张图标
- 多维表格：网格/表格图标
- 视频会议：摄像头图标
- 邮箱：信封图标
- 知识问答：灯泡图标

输出格式（严格JSON，不要markdown）：
{"thought":"逐一扫描列出侧边栏可见图标及其大致Y坐标→找出目标图标→其中心坐标","action":"click|double_click|type|hotkey|scroll","params":{"x":整数,"y":整数},"confidence":0.0-1.0}

规则：
1. 坐标(0,0)是屏幕左上角，输出目标元素中心点
2. 必须逐一列出侧边栏图标，只列你确实看到的
3. 找不到目标元素时confidence=0
4. 绝对不要用markdown代码块，直接输出纯JSON"""

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
            parsed = json.loads(_extract_json(raw))
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
            parsed = json.loads(_extract_json(raw))
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
