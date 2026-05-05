"""DashScope-compatible VLM client for screen analysis and verification."""

from __future__ import annotations

import base64
import io
import json
import re
import time
from dataclasses import dataclass

import httpx
from openai import OpenAI
from PIL import Image

from ..config import config

# 模型要求输入图像各维度至少 10px
VLM_MIN_DIM = 20


def _extract_json(text: str) -> str:
    """从 VLM 响应文本中提取 JSON 字符串（支持 markdown 代码块和裸 JSON）。"""
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


# VLM 系统提示词：用于分析屏幕截图并输出动作 JSON
SYSTEM_PROMPT = """你是 GUI 自动化操作助手。请根据截图和用户指令输出严格 JSON。
当前输入可能是完整窗口截图或局部区域，区域提示会说明截图范围。
允许动作类型：
- click
- double_click
- type
- hotkey
- scroll
- wait
- mouse_move
- drag

单步格式：
{"thought":"...","action":"click","params":{"x":120,"y":220},"confidence":0.92}

动作块格式（推荐用于需要多步完成的指令，如"搜索后输入文字"必须先click再type）：
{"thought":"...","goal":"...","actions":[
  {"action":"click","params":{"x":120,"y":60}},
  {"action":"wait","params":{"ms":200}},
  {"action":"type","params":{"text":"要输入的内容"}}
],"confidence":0.88}

scroll 参数支持 dy（正数下滚负数上滚），或 direction="down"/"up"（默认300像素）；
可选 x/y 指定滚轮前光标应移到哪个坐标（通常在内容区中心），避免滚轮打在不可滚动的区域：
{"action":"scroll","params":{"dy":300,"x":640,"y":400}}

重要规则：
1. 只输出 JSON，不要 markdown。
2. 坐标以当前输入图片左上角为 (0, 0)。
3. 涉及"输入"或"键入"的指令，必须先 click 目标输入框再 type，用动作块格式。
4. region_hint=full_window 表示输入是完整的应用窗口截图，可以在整个范围内定位目标。
5. 如果置信度低，可以先输出更保守的动作，如 mouse_move 或 wait。"""

VERIFY_PROMPT = """你是 GUI 测试验证助手。对比操作前后两张截图，判断操作是否达到预期。
输出严格 JSON：
{"passed": true, "reason": "...", "confidence": 0.0}
只输出 JSON。"""

CONFIRM_TARGET_PROMPT = """你是 GUI 元素识别助手。图片中心位置（十字准星处）有一个 UI 元素。
请识别该元素名称，并判断它是否与用户指令中要求操作的目标一致。
输出严格 JSON：{"element_name":"...","is_target":true/false,"confidence":0.0}
只输出 JSON。"""


VLM_MAX_LONG_SIDE = 1280  # 发送给 VLM 前，将截图最长边缩放到此像素，减少上传和处理时间


def _encode_image(image: Image.Image) -> str:
    """将 PIL Image 缩放并编码为 Base64 JPEG 字符串，用于 VLM API 请求。"""
    w, h = image.size
    longest = max(w, h)
    if longest > VLM_MAX_LONG_SIDE:
        scale = VLM_MAX_LONG_SIDE / longest
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _build_client() -> OpenAI:
    """根据配置创建 OpenAI 兼容客户端实例。"""
    return OpenAI(
        api_key=config.dashscope_api_key,
        base_url=config.base_url,
        timeout=config.request_timeout,
        http_client=httpx.Client(timeout=config.request_timeout, trust_env=False),
    )


def _request_chat_completion(messages: list[dict], label: str) -> str:
    """向 VLM 发起带重试逻辑的请求，失败时抛 RuntimeError。"""
    client = _build_client()
    raw = ""
    for attempt in range(config.max_retries):
        try:
            print(f"[VLM-REQ] {label} attempt={attempt+1}/{config.max_retries} model={config.model_name} ...", flush=True)
            t0 = time.time()
            completion = client.chat.completions.create(
                model=config.model_name,
                messages=messages,
                max_completion_tokens=1024,
            )
            elapsed = time.time() - t0
            raw = completion.choices[0].message.content or ""
            print(f"[VLM-RSP] {label} {elapsed:.1f}s len={len(raw)}", flush=True)
            return raw
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"[VLM-ERR] {label} {elapsed:.1f}s error={exc}", flush=True)
            if attempt < config.max_retries - 1:
                time.sleep(attempt + 1)
                continue
            raise RuntimeError(f"{label} request failed: {exc}") from exc
    return raw


def _image_message_parts(image_b64: str, text: str) -> list[dict]:
    """构造包含图片 Base64 URL 和文本的 OpenAI Vision API 消息体。"""
    return [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        },
        {"type": "text", "text": text},
    ]


@dataclass
class VlmActionResponse:
    """VLM 动作分析响应：包含思考过程、动作类型、参数和置信度。"""
    thought: str
    action: str
    params: dict
    confidence: float
    raw_response: str


@dataclass
class VlmVerifyResponse:
    """VLM 验证响应：判断操作是否达到预期结果。"""
    passed: bool
    reason: str
    confidence: float
    raw_response: str


@dataclass
class VlmStateResponse:
    """VLM 页面状态识别响应：应用是否在视图中及当前页面状态。"""
    app_in_view: bool
    state: str
    reason: str
    confidence: float
    raw_response: str


def analyze_screen(image: Image.Image, instruction: str, region_hint: str = "") -> VlmActionResponse:
    """调用 VLM 分析屏幕截图并返回推荐的动作。

    Args:
        image: 待分析的屏幕截图
        instruction: 用户指令
        region_hint: 区域提示（如 left_nav, content, full_window）
    """
    if image.width < VLM_MIN_DIM or image.height < VLM_MIN_DIM:
        # 图像过小无法被 VLM 分析，返回高置信度 wait 让上层重试其他区域
        return VlmActionResponse(
            thought=f"image too small ({image.width}x{image.height})",
            action="wait",
            params={"ms": 50},
            confidence=0.0,
            raw_response="",
        )
    image_b64 = _encode_image(image)
    raw = _request_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _image_message_parts(
                    image_b64,
                    f"指令: {instruction}\n区域提示: {region_hint or 'full_window'}",
                ),
            },
        ],
        label="analyze_screen",
    )
    parsed = json.loads(_extract_json(raw))
    return VlmActionResponse(
        thought=parsed.get("thought", ""),
        action=parsed.get("action", ""),
        params=parsed.get("params", {}),
        confidence=parsed.get("confidence", 0.0),
        raw_response=raw,
    )


def verify_result(before: Image.Image, after: Image.Image, expected: str) -> VlmVerifyResponse:
    """调用 VLM 对比操作前后截图，判断操作是否达到预期效果。"""
    if before.width < VLM_MIN_DIM or before.height < VLM_MIN_DIM:
        return VlmVerifyResponse(
            passed=False,
            reason=f"before image too small ({before.width}x{before.height}) for VLM verification",
            confidence=0.0,
            raw_response="",
        )
    if after.width < VLM_MIN_DIM or after.height < VLM_MIN_DIM:
        return VlmVerifyResponse(
            passed=False,
            reason=f"after image too small ({after.width}x{after.height}) for VLM verification",
            confidence=0.0,
            raw_response="",
        )
    before_b64 = _encode_image(before)
    after_b64 = _encode_image(after)
    raw = _request_chat_completion(
        messages=[
            {"role": "system", "content": VERIFY_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{before_b64}"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{after_b64}"},
                    },
                    {
                        "type": "text",
                        "text": f"操作前是第一张图，操作后是第二张图。预期结果：{expected}",
                    },
                ],
            },
        ],
        label="verify_result",
    )
    parsed = json.loads(_extract_json(raw))
    return VlmVerifyResponse(
        passed=parsed.get("passed", False),
        reason=parsed.get("reason", ""),
        confidence=parsed.get("confidence", 0.0),
        raw_response=raw,
    )


def classify_page_state(image: Image.Image, known_states: list[str]) -> VlmStateResponse:
    """调用 VLM 识别截图中目标应用是否在视图中及当前页面状态。

    Args:
        image: 待识别的屏幕截图
        known_states: 已知页面状态列表（如 messages, calendar, docs 等）
    """
    if image.width < VLM_MIN_DIM or image.height < VLM_MIN_DIM:
        return VlmStateResponse(
            app_in_view=False,
            state="unknown",
            reason=f"image too small ({image.width}x{image.height}) for VLM classification",
            confidence=0.0,
            raw_response="",
        )
    image_b64 = _encode_image(image)
    state_prompt = (
        "你是桌面自动化状态识别助手。"
        "请判断截图中是否正在显示目标应用飞书/Lark，"
        "并在候选状态中选择当前最接近的页面状态。"
        f"候选状态: {', '.join(known_states)}。"
        '输出严格 JSON: {"app_in_view": true, "state": "...", "reason": "...", "confidence": 0.0}'
    )
    raw = _request_chat_completion(
        messages=[
            {"role": "system", "content": state_prompt},
            {
                "role": "user",
                "content": _image_message_parts(
                    image_b64,
                    "请只根据截图可见内容判断当前页面状态。",
                ),
            },
        ],
        label="classify_page_state",
    )
    parsed = json.loads(_extract_json(raw))
    return VlmStateResponse(
        app_in_view=bool(parsed.get("app_in_view", False)),
        state=parsed.get("state", "unknown"),
        reason=parsed.get("reason", ""),
        confidence=parsed.get("confidence", 0.0),
        raw_response=raw,
    )


@dataclass
class ConfirmTargetResponse:
    """点击前目标确认响应：识别十字准星处的 UI 元素是否与指令目标匹配。"""
    element_name: str
    is_target: bool
    confidence: float
    raw_response: str


def confirm_click_target(patch: Image.Image, instruction: str) -> ConfirmTargetResponse:
    """在点击执行前，裁剪目标点周围区域让 VLM 确认十字准星处是否为预期元素。

    Args:
        patch: 目标点周围 60x60 区域的截图
        instruction: 用户指令
    """
    if patch.width < VLM_MIN_DIM or patch.height < VLM_MIN_DIM:
        return ConfirmTargetResponse(
            element_name="",
            is_target=False,
            confidence=0.0,
            raw_response="",
        )
    image_b64 = _encode_image(patch)
    try:
        raw = _request_chat_completion(
            messages=[
                {"role": "system", "content": CONFIRM_TARGET_PROMPT},
                {
                    "role": "user",
                    "content": _image_message_parts(
                        image_b64,
                        f"指令: {instruction}\n图片中心（十字准星处）是什么 UI 元素？它是否是指令要求操作的目标？",
                    ),
                },
            ],
            label="confirm_click_target",
        )
    except Exception:
        # 确认调用失败时放行，避免阻塞主流程
        return ConfirmTargetResponse(
            element_name="",
            is_target=True,
            confidence=0.0,
            raw_response="",
        )
    parsed = json.loads(_extract_json(raw))
    return ConfirmTargetResponse(
        element_name=parsed.get("element_name", ""),
        is_target=parsed.get("is_target", False),
        confidence=parsed.get("confidence", 0.0),
        raw_response=raw,
    )
