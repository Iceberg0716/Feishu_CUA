from __future__ import annotations

import unittest

from runtime.recorded_skill_loader import RecordedSkillLoader
from runtime.recorded_skill_registry import RecordedSkillRegistry


class TestRecordedSkillRegistry(unittest.TestCase):
    def _build_registry(self) -> RecordedSkillRegistry:
        loader = RecordedSkillLoader()
        skills = loader.load_dir("recorded_skills")
        return RecordedSkillRegistry(skills)

    def test_registry_scans_recorded_skills(self) -> None:
        reg = self._build_registry()
        ids = [s.id for s in reg.list()]
        self.assertIn("recorded.im.open_chat_by_search.v1", ids)

    def test_find_by_intent(self) -> None:
        reg = self._build_registry()
        found = reg.find_by_intent("im", "open_chat")
        self.assertTrue(found)
        self.assertEqual(found[0].id, "recorded.im.open_chat_by_search.v1")

    def test_find_by_intent_mention_member(self) -> None:
        reg = self._build_registry()
        found = reg.find_by_intent("im", "mention_member")
        self.assertTrue(found)
        self.assertEqual(found[0].id, "recorded.im.mention_member_in_current_chat.v1")

    def test_find_by_postcondition(self) -> None:
        reg = self._build_registry()
        found = reg.find_by_postcondition("active_chat_opened")
        self.assertTrue(found)
        self.assertEqual(found[0].id, "recorded.im.open_chat_by_search.v1")

    def test_find_compatible_reasons(self) -> None:
        reg = self._build_registry()
        matches = reg.find_compatible("im", "open_chat", params={}, current_state=[])
        self.assertTrue(matches)
        self.assertFalse(matches[0].compatible)
        self.assertTrue(any("missing_params:chat_name" in r for r in matches[0].reasons))
        self.assertTrue(any("unmet_preconditions:feishu_window_available" in r for r in matches[0].reasons))


if __name__ == "__main__":
    unittest.main()
