"""Task planning: break complex instructions into ordered steps."""

import json
from dataclasses import dataclass

from PIL import Image

from ..perception.vlm_client import call_vlm_for_plan


@dataclass
class PlanStep:
    index: int
    description: str
    expected: str


@dataclass
class TaskPlan:
    instruction: str
    steps: list[PlanStep]


def create_plan(image: Image.Image, instruction: str) -> TaskPlan:
    """Use VLM to decompose a complex instruction into ordered single-action steps."""
    raw = call_vlm_for_plan(image, instruction)
    steps_data = json.loads(raw)

    if isinstance(steps_data, dict):
        steps_data = [steps_data]

    steps = []
    for i, s in enumerate(steps_data):
        steps.append(PlanStep(
            index=i + 1,
            description=s.get("description", ""),
            expected=s.get("expected", ""),
        ))

    return TaskPlan(instruction=instruction, steps=steps)
