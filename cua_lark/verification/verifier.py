"""Verification of action results via VLM semantic comparison."""

from dataclasses import dataclass

from PIL import Image

from ..perception.vlm_client import verify_result as vlm_verify


@dataclass
class Verdict:
    passed: bool
    reason: str
    confidence: float


def verify(
    before: Image.Image, after: Image.Image, expected: str
) -> Verdict:
    """Compare before/after screenshots to check if action succeeded."""
    result = vlm_verify(before, after, expected)
    return Verdict(
        passed=result.passed,
        reason=result.reason,
        confidence=result.confidence,
    )
