from __future__ import annotations

import unittest

from runtime.recorded_skill_loader import RecordedSkillLoader


class TestRecordedSkillLoader(unittest.TestCase):
    def test_loader_can_read_open_chat_yaml(self) -> None:
        loader = RecordedSkillLoader()
        skill = loader.load_path("recorded_skills/im/open_chat_by_search.yaml")
        self.assertEqual(skill.id, "recorded.im.open_chat_by_search.v1")
        self.assertEqual(skill.type, "recorded_skill")
        self.assertEqual(skill.metadata.product, "im")
        self.assertEqual(skill.metadata.intent, "open_chat")
        self.assertFalse(skill.metadata.side_effect)
        self.assertTrue(len(skill.steps) >= 1)


if __name__ == "__main__":
    unittest.main()

