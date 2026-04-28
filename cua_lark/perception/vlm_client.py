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
3. type动作如果要输入到特定输入框，必须带上x,y指定该输入框的位置（系统会先点击再输入）
4. 找不到目标元素时confidence=0
5. 绝对不要用markdown代码块，直接输出纯JSON"""

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


PLAN_PROMPT = """你是一个任务规划助手。根据屏幕截图和用户指令，将指令拆解为有序的操作步骤。每个步骤必须是一个独立的单步操作（点击某个元素、输入文字、按快捷键等）。

输出JSON数组，每个元素包含：
{
  "description": "这一步骤的操作指令（自然语言，可以独立执行）",
  "expected": "执行后预期看到的变化"
}

规则：
1. 如果指令是"在XX输入YY"，必须拆成两步：[点击输入框, 输入YY]
2. 步骤之间的先后顺序要合理，前一步的预期结果应为后一步创造前提
3. 不要包含等待操作，系统会自动等待
4. 只输出JSON数组，不要markdown"""

HEAL_PROMPT = """你是一个GUI调试助手。上一个操作失败了，你需要分析当前截图，找出失败原因，并生成一个新的替代操作。

输出格式（严格JSON）：
{
  "reason": "为什么原操作失败",
  "alternative": "新的操作指令（自然语言，可以独立执行）"
}

只输出JSON，不要markdown。"""


def call_vlm_for_plan(image: Image.Image, instruction: str) -> str:
    """Break instruction into step sequence. Returns raw JSON array string."""
    client = _build_client()
    image_b64 = _encode_image(image)

    user_msg = f"请将以下指令拆解为操作步骤：\n{instruction}"

    for attempt in range(config.max_retries):
        try:
            response = client.chat.completions.create(
                model=config.model_name,
                messages=[
                    {"role": "system", "content": [{"type": "text", "text": PLAN_PROMPT}]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            {"type": "text", "text": user_msg},
                        ],
                    },
                ],
            )
            raw = response.choices[0].message.content
            return _extract_json(raw)
        except Exception:
            if attempt < config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise


def call_vlm_for_heal(
    image: Image.Image, original_step: str, fail_reason: str
) -> tuple[str, str]:
    """Analyze failure and suggest alternative. Returns (reason, alternative_instruction)."""
    client = _build_client()
    image_b64 = _encode_image(image)

    user_msg = f"""原始操作：{original_step}
验证失败原因：{fail_reason}

请分析当前截图，判断失败原因并给出替代操作。"""

    for attempt in range(config.max_retries):
        try:
            response = client.chat.completions.create(
                model=config.model_name,
                messages=[
                    {"role": "system", "content": [{"type": "text", "text": HEAL_PROMPT}]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            {"type": "text", "text": user_msg},
                        ],
                    },
                ],
            )
            raw = response.choices[0].message.content
            parsed = json.loads(_extract_json(raw))
            return parsed.get("reason", ""), parsed.get("alternative", "")
        except (json.JSONDecodeError, KeyError):
            if attempt < config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt < config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise
