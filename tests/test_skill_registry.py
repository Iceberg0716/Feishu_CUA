from __future__ import annotations

import unittest

from skills.base import BaseSkill, SkillResult
from skills.registry import SkillRegistry


class _DummySkill(BaseSkill):
    name = "x"
    description = "d"
    input_schema = {}

    def execute(self, params, context):  # noqa: ANN001
        return SkillResult(success=True)


class TestSkillRegistry(unittest.TestCase):
    def test_register_get_and_duplicate(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill())
        self.assertEqual(reg.get("x").name, "x")
        with self.assertRaises(ValueError):
            reg.register(_DummySkill())


if __name__ == "__main__":
    unittest.main()

