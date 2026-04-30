"""Page state classification from screenshots."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from ..knowledge_base import AppKnowledge
from .vlm_client import classify_page_state


@dataclass
class PageState:
    app_in_view: bool
    state: str
    confidence: float
    reason: str
    raw_response: str


def classify_state(image: Image.Image, knowledge: AppKnowledge) -> PageState:
    result = classify_page_state(image, known_states=list(knowledge.known_page_states))
    state = result.state if result.state in knowledge.known_page_states else "unknown"
    return PageState(
        app_in_view=result.app_in_view,
        state=state,
        confidence=result.confidence,
        reason=result.reason,
        raw_response=result.raw_response,
    )
