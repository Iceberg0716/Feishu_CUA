from __future__ import annotations

import unittest

from agent.planner import RulePlanner


class TestRulePlanner(unittest.TestCase):
    def test_im_plan(self) -> None:
        tc = {"id": "im1", "product": "im", "instruction": "send", "params": {"chat_name": "c", "message": "m"}}
        plan = RulePlanner().build_plan(tc)
        self.assertEqual(plan.steps[0].name, "im.send_message")

    def test_docs_plan(self) -> None:
        tc = {"id": "d1", "product": "docs", "instruction": "create", "params": {"doc_name": "n", "title": "t", "body": "b"}}
        plan = RulePlanner().build_plan(tc)
        self.assertEqual(plan.steps[0].name, "docs.create_document")


if __name__ == "__main__":
    unittest.main()

