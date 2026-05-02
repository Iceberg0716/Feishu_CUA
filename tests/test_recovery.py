"""Unit tests for recovery flow."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from cua_lark.execution.action_types import HotkeyAction
from cua_lark.execution.recovery import ensure_target_app_focused, navigate_to_state, recover_to_known_state
from cua_lark.knowledge_base import load_app_knowledge


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.knowledge = load_app_knowledge("knowledge/feishu.json")

    def test_ensure_target_app_focused_returns_success_when_already_foreground(self) -> None:
        with patch("cua_lark.execution.recovery.is_target_app_in_foreground", return_value=True):
            result = ensure_target_app_focused(self.knowledge)
        self.assertTrue(result.recovered)
        self.assertTrue(result.attempted)

    def test_navigate_to_state_uses_knowledge_sequence(self) -> None:
        executed: list[HotkeyAction] = []

        def fake_execute(action):
            executed.append(action)

        with patch("cua_lark.execution.recovery.execute", side_effect=fake_execute):
            result = navigate_to_state("messages", self.knowledge)

        self.assertTrue(result.recovered)
        self.assertEqual(len(executed), 1)
        self.assertIsInstance(executed[0], HotkeyAction)
        self.assertEqual(executed[0].keys, ["ctrl", "1"])

    def test_navigate_to_state_returns_failure_when_missing_strategy(self) -> None:
        knowledge = self.knowledge.__class__(
            app_names=self.knowledge.app_names,
            launch_commands=self.knowledge.launch_commands,
            known_page_states=self.knowledge.known_page_states,
            stable_home_state=self.knowledge.stable_home_state,
            state_navigation_hotkeys={},
            region_preferences=self.knowledge.region_preferences,
            validation_policies=self.knowledge.validation_policies,
            recovery_sequences={"global": [], "state_entry": {}},
            task_templates=self.knowledge.task_templates,
        )
        result = navigate_to_state("messages", knowledge)
        self.assertFalse(result.recovered)

    def test_recover_to_known_state_runs_global_then_state_entry(self) -> None:
        executed_keys: list[list[str]] = []

        def fake_execute(action):
            executed_keys.append(action.keys)

        with patch("cua_lark.execution.recovery.is_target_app_in_foreground", return_value=True), patch(
            "cua_lark.execution.recovery.execute",
            side_effect=fake_execute,
        ):
            result = recover_to_known_state("test", self.knowledge, current_state="calendar")

        self.assertTrue(result.recovered)
        self.assertEqual(executed_keys, [["esc"], ["ctrl", "1"]])


if __name__ == "__main__":
    unittest.main()
