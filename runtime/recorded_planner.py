from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.planning_result import MissingCapabilityResult, RecordedPlanResult, RecordedPlanSkillStep
from runtime.recorded_skill_registry import RecordedSkillRegistry


@dataclass(frozen=True, slots=True)
class _SubgoalSpec:
    product: str
    intent: str
    required_params: list[str]
    suggested_recorded_skill_id: str | None
    suggested_preconditions: list[str]
    suggested_postconditions: list[str]


class RecordedPlanner:
    def __init__(self, *, registry: RecordedSkillRegistry) -> None:
        self._registry = registry

    def plan(
        self,
        *,
        product: str,
        intent: str,
        params: dict[str, Any] | None = None,
        current_state: list[str] | set[str] | None = None,
    ) -> RecordedPlanResult:
        given_params = dict(params or {})
        state: set[str] = set(current_state or [])

        subgoals = self._expand_subgoals(product=product, intent=intent)
        if not subgoals:
            # Fallback: treat intent itself as a single subgoal.
            subgoals = [
                _SubgoalSpec(
                    product=product,
                    intent=intent,
                    required_params=sorted(list(self._infer_required_params(product=product, intent=intent))),
                    suggested_recorded_skill_id=f"recorded.{product}.{intent}.v1",
                    suggested_preconditions=sorted(list(state)),
                    suggested_postconditions=[],
                )
            ]

        steps: list[RecordedPlanSkillStep | MissingCapabilityResult] = []

        for sg in subgoals:
            missing_params = sorted([p for p in sg.required_params if p not in given_params])
            if missing_params:
                if sg.suggested_preconditions:
                    state_list = sorted([s for s in state if s in set(sg.suggested_preconditions)])
                else:
                    state_list = sorted(state)
                steps.append(
                    MissingCapabilityResult(
                        product=sg.product,
                        intent=sg.intent,
                        required_params=list(sg.required_params),
                        current_state=state_list,
                        missing_reason=f"Missing required params for intent={sg.intent}: {','.join(missing_params)}.",
                        missing_reason_code="missing_params",
                        suggested_recorded_skill_id=sg.suggested_recorded_skill_id,
                        suggested_preconditions=list(sg.suggested_preconditions),
                        suggested_postconditions=list(sg.suggested_postconditions),
                    )
                )
                return RecordedPlanResult(
                    product=product,
                    intent=intent,
                    steps=steps,
                    current_state=state_list,
                    complete=False,
                    incomplete_reason=f"missing_params:{sg.product}/{sg.intent}",
                )

            compat = self._registry.find_compatible(sg.product, sg.intent, given_params, state)
            best = next((c for c in compat if c.compatible), None)
            if best is None:
                if sg.suggested_preconditions:
                    state_list = sorted([s for s in state if s in set(sg.suggested_preconditions)])
                else:
                    state_list = sorted(state)
                steps.append(
                    MissingCapabilityResult(
                        product=sg.product,
                        intent=sg.intent,
                        required_params=list(sg.required_params),
                        current_state=state_list,
                        missing_reason=(
                            f"No compatible recorded skill found for product={sg.product} intent={sg.intent} "
                            f"with current_state={','.join(state_list) if state_list else '(empty)'}."
                        ),
                        missing_reason_code="no_compatible_recorded_skill",
                        suggested_recorded_skill_id=sg.suggested_recorded_skill_id,
                        suggested_preconditions=list(sg.suggested_preconditions),
                        suggested_postconditions=list(sg.suggested_postconditions),
                    )
                )
                return RecordedPlanResult(
                    product=product,
                    intent=intent,
                    steps=steps,
                    current_state=state_list,
                    complete=False,
                    incomplete_reason=f"missing_capability:{sg.product}/{sg.intent}",
                )

            skill = best.skill
            steps.append(
                RecordedPlanSkillStep(
                    product=sg.product,
                    intent=sg.intent,
                    recorded_skill_id=skill.id,
                    params={k: given_params.get(k) for k in sorted(skill.required_params()) if k in given_params},
                    preconditions=list(skill.preconditions or []),
                    postconditions=list(skill.postconditions or []),
                    side_effect=bool(skill.metadata.side_effect),
                )
            )
            for post in skill.postconditions or []:
                state.add(post)

        return RecordedPlanResult(
            product=product,
            intent=intent,
            steps=steps,
            current_state=sorted(state),
            complete=True,
            incomplete_reason=None,
        )

    def _expand_subgoals(self, *, product: str, intent: str) -> list[_SubgoalSpec]:
        if product != "im":
            return []

        if intent == "send_message":
            return [
                _SubgoalSpec(
                    product="im",
                    intent="open_chat",
                    required_params=["chat_name"],
                    suggested_recorded_skill_id="recorded.im.open_chat_by_search.v1",
                    suggested_preconditions=["feishu_window_available"],
                    suggested_postconditions=["active_chat_opened"],
                ),
                _SubgoalSpec(
                    product="im",
                    intent="send_text",
                    required_params=["message"],
                    suggested_recorded_skill_id="recorded.im.send_text_in_current_chat.v1",
                    suggested_preconditions=["active_chat_opened"],
                    suggested_postconditions=["message_sent"],
                ),
            ]

        if intent == "send_emoji":
            return [
                _SubgoalSpec(
                    product="im",
                    intent="open_chat",
                    required_params=["chat_name"],
                    suggested_recorded_skill_id="recorded.im.open_chat_by_search.v1",
                    suggested_preconditions=["feishu_window_available"],
                    suggested_postconditions=["active_chat_opened"],
                ),
                _SubgoalSpec(
                    product="im",
                    intent="send_emoji",
                    required_params=["emoji_name"],
                    suggested_recorded_skill_id="recorded.im.send_emoji_in_current_chat.v1",
                    suggested_preconditions=["active_chat_opened"],
                    suggested_postconditions=["emoji_sent"],
                ),
            ]

        if intent == "mention_member":
            return [
                _SubgoalSpec(
                    product="im",
                    intent="open_chat",
                    required_params=["chat_name"],
                    suggested_recorded_skill_id="recorded.im.open_chat_by_search.v1",
                    suggested_preconditions=["feishu_window_available"],
                    suggested_postconditions=["active_chat_opened"],
                ),
                _SubgoalSpec(
                    product="im",
                    intent="mention_member",
                    required_params=["member_name", "message"],
                    suggested_recorded_skill_id="recorded.im.mention_member_in_current_chat.v1",
                    suggested_preconditions=["active_chat_opened"],
                    suggested_postconditions=["mention_message_sent"],
                ),
            ]

        return []

    def _infer_required_params(self, *, product: str, intent: str) -> set[str]:
        candidates = self._registry.find_by_intent(product, intent)
        if not candidates:
            return set()
        required: set[str] = set()
        for s in candidates:
            required |= s.required_params()
        return required


__all__ = ["RecordedPlanner"]
