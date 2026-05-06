from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from runtime.recorded_skill_registry import RecordedSkillRegistry


class NLSubgoal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str
    intent: str
    params: dict[str, Any] = Field(default_factory=dict)


class NLPlan(BaseModel):
    """
    LLM-returned plan. Must only contain semantic fields (no tool calls).
    """

    model_config = ConfigDict(extra="forbid")

    status: str
    product: str | None = None
    intent: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    subgoals: list[NLSubgoal] = Field(default_factory=list)
    confidence: float | None = None


class NLTaskIntent(BaseModel):
    """
    LLM-returned task intent (no subgoals). Used by step-by-step runner to decide which
    composite policy to apply.
    """

    model_config = ConfigDict(extra="forbid")

    status: str
    product: str | None = None
    intent: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None


class NLNextSubgoalPlan(BaseModel):
    """
    LLM-returned next-subgoal plan (single subgoal only).
    """

    model_config = ConfigDict(extra="forbid")

    status: str
    subgoal: NLSubgoal | None = None
    confidence: float | None = None


class TextLLM(Protocol):
    def chat_json(self, *, system_prompt: str, user_prompt: str, timeout_seconds: int = 30) -> str:
        """
        Returns model content (expected to be strict JSON text).
        """


def _json_extract_first_object(text: str) -> str:
    """
    Best-effort extraction of the first JSON object in a string.
    The system prompt requires "JSON only", but we still guard against wrappers.
    """
    s = text.strip()
    if s.startswith("{") and s.endswith("}"):
        return s
    start = s.find("{")
    if start < 0:
        raise ValueError("LLM output does not contain a JSON object")
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    raise ValueError("LLM output contains an incomplete JSON object")


class LLMPlanner:
    """
    High-level semantic planner:
    - injects recorded skill catalog into prompt
    - asks LLM to output strict JSON plan (product/intent/params/subgoals only)
    """

    def __init__(self, *, llm: TextLLM) -> None:
        self._llm = llm

    def build_catalog(self, *, registry: RecordedSkillRegistry) -> list[dict[str, Any]]:
        catalog: list[dict[str, Any]] = []
        for skill in registry.list():
            catalog.append(
                {
                    "skill_id": skill.id,
                    "product": skill.metadata.product,
                    "intent": skill.metadata.intent,
                    "params": sorted(list(skill.params.keys())),
                    "required_params": sorted(list(skill.required_params())),
                    "preconditions": list(skill.preconditions or []),
                    "postconditions": list(skill.postconditions or []),
                    "side_effect": bool(skill.metadata.side_effect),
                    "status": skill.metadata.status,
                }
            )
        return catalog

    def plan(
        self,
        *,
        instruction: str,
        registry: RecordedSkillRegistry,
        timeout_seconds: int = 30,
    ) -> NLPlan:
        if not instruction.strip():
            raise ValueError("instruction is empty")

        catalog = self.build_catalog(registry=registry)
        catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2)

        system_prompt = (
            "You are the high-level semantic planner for a CUA-Lark test agent.\n"
            "Convert the user's natural language instruction into a STRICT JSON plan.\n"
            "You MUST ONLY output JSON (no markdown, no extra text).\n"
            "Allowed top-level keys: status, product, intent, params, subgoals, confidence.\n"
            "Allowed subgoal keys: product, intent, params.\n"
            "Do NOT output any other keys (e.g. do NOT include: reason, explanation, steps, skill_id, recorded_skill_id).\n"
            "status MUST be one of: ok, missing_capability, clarification_required, missing_params.\n"
            "If status=ok, subgoals MUST be a non-empty list.\n"
            "You MUST NOT output any GUI actions, tools, coordinates, clicks, hotkeys, typing steps,\n"
            "pyautogui/pywinauto code, provider calls, or any tool invocation.\n"
            "Execution policy (IMPORTANT):\n"
            "- For IM send-message tasks, ALWAYS plan in this exact order: open_chat -> send_text.\n"
            "  Even if the chat might already be open, ALWAYS include open_chat first.\n"
            "- For IM mention-member tasks, ALWAYS plan in this exact order: open_chat -> mention_member.\n"
            "- For IM send-emoji tasks, ALWAYS plan in this exact order: open_chat -> send_emoji.\n"
            "For IM tasks that require opening a chat, use a semantic subgoal intent like 'open_chat'.\n"
            "NOTE: Opening an IM chat is handled by recorded skills that may use the Ctrl+K search UI internally.\n"
            "Select product/intent and params ONLY from the provided Skill Catalog.\n"
            "If capability is missing, set status=missing_capability.\n"
            "If required params are missing/ambiguous, set status=clarification_required.\n"
        )
        user_prompt = (
            "Skill Catalog (recorded skills):\n"
            f"{catalog_json}\n\n"
            "User instruction:\n"
            f"{instruction}\n\n"
            "Return strict JSON only."
        )

        raw = self._llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, timeout_seconds=timeout_seconds)
        obj_text = _json_extract_first_object(str(raw))
        try:
            data = json.loads(obj_text)
        except Exception as exc:
            raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
        return NLPlan.model_validate(data)

    def plan_intent(
        self,
        *,
        instruction: str,
        registry: RecordedSkillRegistry,
        timeout_seconds: int = 30,
    ) -> NLTaskIntent:
        """
        Step-by-step mode entrypoint: classify the task (product/intent) and extract params.
        Does NOT output subgoals.
        """
        if not instruction.strip():
            raise ValueError("instruction is empty")

        catalog = self.build_catalog(registry=registry)
        catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2)

        system_prompt = (
            "You are the semantic intent parser for a CUA-Lark test agent.\n"
            "Convert the user's natural language instruction into STRICT JSON.\n"
            "You MUST ONLY output JSON (no markdown, no extra text).\n"
            "Allowed top-level keys: status, product, intent, params, confidence.\n"
            "Do NOT output any other keys.\n"
            "status MUST be one of: ok, missing_capability, clarification_required, missing_params.\n"
            "You MUST NOT output any GUI actions, tools, coordinates, clicks, hotkeys, typing steps,\n"
            "pyautogui/pywinauto code, provider calls, or any tool invocation.\n"
            "Select product/intent and params ONLY from the provided Skill Catalog.\n"
            "Prefer recorded skills (catalog entries) and prefer composite IM intents like send_message when the user asks to send a message.\n"
        )
        user_prompt = (
            "Skill Catalog (recorded skills):\n"
            f"{catalog_json}\n\n"
            "User instruction:\n"
            f"{instruction}\n\n"
            "Return strict JSON only."
        )

        raw = self._llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, timeout_seconds=timeout_seconds)
        obj_text = _json_extract_first_object(str(raw))
        try:
            data = json.loads(obj_text)
        except Exception as exc:
            raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
        return NLTaskIntent.model_validate(data)

    def plan_next_subgoal(
        self,
        *,
        instruction: str,
        registry: RecordedSkillRegistry,
        required_product: str,
        required_intent: str,
        known_params: dict[str, Any] | None = None,
        current_state: list[str] | None = None,
        last_step: dict[str, Any] | None = None,
        timeout_seconds: int = 30,
    ) -> NLNextSubgoalPlan:
        """
        Step-by-step replanning: ask the LLM to output exactly ONE next subgoal.
        The runner enforces (required_product, required_intent); the LLM should focus on params only.
        """
        if not instruction.strip():
            raise ValueError("instruction is empty")

        catalog = self.build_catalog(registry=registry)
        catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2)
        required_product = str(required_product).strip().lower()
        required_intent = str(required_intent).strip()
        kp = dict(known_params or {})
        state_list = list(current_state or [])
        last_step_obj = dict(last_step or {})

        system_prompt = (
            "You are the step-by-step semantic replanner for a CUA-Lark test agent.\n"
            "You MUST ONLY output JSON (no markdown, no extra text).\n"
            "Allowed top-level keys: status, subgoal, confidence.\n"
            "subgoal MUST be an object with keys: product, intent, params.\n"
            "Do NOT output any other keys.\n"
            "status MUST be one of: ok, missing_capability, clarification_required, missing_params.\n"
            "You MUST NOT output any GUI actions, tools, coordinates, clicks, hotkeys, typing steps,\n"
            "pyautogui/pywinauto code, provider calls, or any tool invocation.\n"
            f"REQUIRED next subgoal: product='{required_product}', intent='{required_intent}'.\n"
            "You MUST set subgoal.product and subgoal.intent to exactly the required values.\n"
            "Select params ONLY from the provided Skill Catalog.\n"
        )
        user_prompt = (
            "Skill Catalog (recorded skills):\n"
            f"{catalog_json}\n\n"
            "User instruction:\n"
            f"{instruction}\n\n"
            "Known task params (may be incomplete):\n"
            f"{json.dumps(kp, ensure_ascii=False, indent=2)}\n\n"
            "Current state:\n"
            f"{json.dumps(state_list, ensure_ascii=False)}\n\n"
            "Last step result (if any):\n"
            f"{json.dumps(last_step_obj, ensure_ascii=False, indent=2)}\n\n"
            "Return strict JSON only."
        )

        raw = self._llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, timeout_seconds=timeout_seconds)
        obj_text = _json_extract_first_object(str(raw))
        try:
            data = json.loads(obj_text)
        except Exception as exc:
            raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
        return NLNextSubgoalPlan.model_validate(data)


__all__ = ["LLMPlanner", "NLPlan", "NLSubgoal", "NLTaskIntent", "NLNextSubgoalPlan", "TextLLM"]
