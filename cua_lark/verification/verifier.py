"""Verification of action results via VLM semantic comparison."""

from dataclasses import dataclass

from PIL import Image

from ..perception.vlm_client import verify_result as vlm_verify


@dataclass
class Verdict:
    """验证结论：操作是否达到预期。"""
    passed: bool
    reason: str
    confidence: float


def verify(
    before: Image.Image, after: Image.Image, expected: str
) -> Verdict:
    """对比操作前后的截图，通过 VLM 判断操作是否达到预期效果。"""
    result = vlm_verify(before, after, expected)
    return Verdict(
        passed=result.passed,
        reason=result.reason,
        confidence=result.confidence,
    )
