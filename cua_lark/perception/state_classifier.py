"""Page state classification from screenshots."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from ..knowledge_base import AppKnowledge
from .vlm_client import classify_page_state


@dataclass
class PageState:
    """页面状态识别结果。"""
    app_in_view: bool      # 目标应用是否在截图中可见
    state: str             # 当前页面状态标签
    confidence: float       # VLM 置信度
    reason: str
    raw_response: str


def classify_state(image: Image.Image, knowledge: AppKnowledge) -> PageState:
    """调用 VLM 识别截图的页面状态，并将结果对齐到知识库中已知的状态列表。"""
    result = classify_page_state(image, known_states=list(knowledge.known_page_states))
    state = result.state if result.state in knowledge.known_page_states else "unknown"
    return PageState(
        app_in_view=result.app_in_view,
        state=state,
        confidence=result.confidence,
        reason=result.reason,
        raw_response=result.raw_response,
    )
