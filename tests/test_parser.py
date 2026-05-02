"""Unit tests for action parsing."""

from __future__ import annotations

import unittest

from cua_lark.execution.action_types import ActionChunk, ClickAction, DragAction, HotkeyAction
from cua_lark.execution.parser import _extract_json, parse_action


class ParserTests(unittest.TestCase):
    def test_extract_json_from_fenced_block(self) -> None:
        text = """analysis

```json
{"action":"click","params":{"x":10,"y":20}}
```
"""
        self.assertEqual(
            _extract_json(text),
            '{"action":"click","params":{"x":10,"y":20}}',
        )

    def test_parse_action_clamps_coordinates(self) -> None:
        action = parse_action(
            '{"action":"click","params":{"x":9999,"y":-5,"button":"right"}}',
            1920,
            1080,
        )
        self.assertIsInstance(action, ClickAction)
        self.assertEqual(action.x, 1920)
        self.assertEqual(action.y, 0)
        self.assertEqual(action.button, "right")

    def test_parse_hotkey_accepts_string(self) -> None:
        action = parse_action(
            '{"action":"hotkey","params":{"keys":"ctrl+shift+k"}}',
            100,
            100,
        )
        self.assertIsInstance(action, HotkeyAction)
        self.assertEqual(action.keys, ["ctrl", "shift", "k"])

    def test_parse_action_chunk_preserves_flags(self) -> None:
        action = parse_action(
            """
            {
              "goal": "move then drag",
              "actions": [
                {"action": "hotkey", "params": {"keys": ["ctrl", "1"]}},
                {"action": "drag", "params": {"start_x": 1, "start_y": 2, "end_x": 300, "end_y": 400}}
              ],
              "verify_each_step": true,
              "stop_on_failure": false
            }
            """,
            200,
            300,
        )
        self.assertIsInstance(action, ActionChunk)
        self.assertTrue(action.verify_each_step)
        self.assertFalse(action.stop_on_failure)
        self.assertIsInstance(action.actions[1], DragAction)
        drag = action.actions[1]
        self.assertEqual((drag.start_x, drag.start_y, drag.end_x, drag.end_y), (1, 2, 200, 300))


if __name__ == "__main__":
    unittest.main()
