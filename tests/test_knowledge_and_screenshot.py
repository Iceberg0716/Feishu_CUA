"""Unit tests for knowledge loading and screenshot helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cua_lark.execution.action_types import ActionChunk, ScrollAction, TypeAction
from cua_lark.knowledge_base import load_app_knowledge
from cua_lark.orchestrator import Orchestrator
from cua_lark.perception.screenshot import Screenshot, WindowBounds


class KnowledgeAndScreenshotTests(unittest.TestCase):
    def test_load_app_knowledge_reads_template_conditions(self) -> None:
        knowledge = load_app_knowledge("knowledge/feishu.json")
        self.assertIn("Feishu", knowledge.app_names)
        self.assertEqual(knowledge.stable_home_state, "messages")
        search_template = next(item for item in knowledge.task_templates if item["name"] == "search_text")
        self.assertIn("preconditions", search_template)
        self.assertIn("postconditions", search_template)
        self.assertEqual(search_template["slots"]["text"]["pattern"], "输入\\s+(.+)$")

    def test_load_app_knowledge_contains_specialized_feishu_templates(self) -> None:
        knowledge = load_app_knowledge("knowledge/feishu.json")
        names = {item["name"] for item in knowledge.task_templates}
        self.assertTrue(
            {
                "open_conversation",
                "send_message_to_target",
                "create_calendar_event_title",
                "open_document_by_name",
                "scroll_current_message_list_down",
                "open_recent_document",
            }.issubset(names)
        )
        self.assertIn("conversation", knowledge.region_preferences)
        self.assertIn("calendar_editor", knowledge.region_preferences)
        self.assertIn("docs_list", knowledge.region_preferences)

    def test_template_slots_clean_feishu_task_modifiers(self) -> None:
        orch = object.__new__(Orchestrator)
        orch.knowledge = load_app_knowledge("knowledge/feishu.json")

        action, _, template, slots = orch._template_action_for_instruction(
            "给 测试群 发送消息 ：上线完成 并停留1秒",
            "messages",
            True,
            1280,
            720,
        )
        self.assertEqual(template["name"], "send_message_to_target")
        self.assertEqual(slots, {"target": "测试群", "message": "上线完成"})
        self.assertIsInstance(action, ActionChunk)
        self.assertTrue(any(isinstance(item, TypeAction) and item.text == "上线完成" for item in action.actions))

        action, _, template, slots = orch._template_action_for_instruction(
            "创建日程 项目同步会 时间 明天10点",
            "messages",
            True,
            1280,
            720,
        )
        self.assertEqual(template["name"], "create_calendar_event_title")
        self.assertEqual(slots["title"], "项目同步会")

        action, _, template, slots = orch._template_action_for_instruction(
            "在当前消息列表向下滚动",
            "messages",
            True,
            1280,
            720,
        )
        self.assertEqual(template["name"], "scroll_current_message_list_down")
        self.assertTrue(any(isinstance(item, ScrollAction) and item.dy < 0 for item in action.actions))

    def test_crop_foreground_window_uses_bounds(self) -> None:
        screenshot = Screenshot(output_dir=tempfile.mkdtemp())
        image = Image.new("RGB", (400, 300), color=(255, 255, 255))
        with patch("cua_lark.perception.screenshot.get_foreground_window_bounds", return_value=WindowBounds(10, 20, 110, 220)):
            cropped, bounds = screenshot.crop_foreground_window(image)
        self.assertEqual(cropped.size, (100, 200))
        self.assertEqual(bounds, WindowBounds(10, 20, 110, 220))

    def test_split_zones_returns_expected_layout(self) -> None:
        screenshot = Screenshot(output_dir=tempfile.mkdtemp())
        zones = screenshot.split_zones(Image.new("RGB", (1000, 500), color=(0, 0, 0)))
        self.assertEqual(zones.left_nav, (0, 0, 180, 500))
        self.assertEqual(zones.top_bar, (0, 0, 1000, 60))
        self.assertEqual(zones.content, (180, 60, 1000, 500))

    def test_mark_step_deletes_files_and_updates_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            screenshot = Screenshot(output_dir=tmp)
            before = screenshot.session_dir / "before.png"
            after = screenshot.session_dir / "after.png"
            before.write_bytes(b"1")
            after.write_bytes(b"2")
            screenshot._entries = [
                {"path": str(before), "role": "before"},
                {"path": str(after), "role": "after"},
            ]
            screenshot.mark_step(str(before), str(after), keep=False, verdict="PASS")
            self.assertFalse(before.exists())
            self.assertFalse(after.exists())
            payload = json.loads(screenshot.index_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["entries"], [])
            self.assertEqual(payload["last_verdict"], "PASS")

    def test_mark_step_deletes_extra_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            screenshot = Screenshot(output_dir=tmp)
            before = screenshot.session_dir / "before.png"
            after = screenshot.session_dir / "after.png"
            extra = screenshot.session_dir / "before_recovered.png"
            for path in (before, after, extra):
                path.write_bytes(b"x")
            screenshot._entries = [
                {"path": str(before), "role": "before"},
                {"path": str(after), "role": "after"},
                {"path": str(extra), "role": "before_recovered"},
            ]
            screenshot.mark_step(str(before), str(after), keep=False, verdict="PASS", extra_paths=[str(extra)])
            self.assertFalse(extra.exists())
            payload = json.loads(screenshot.index_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["entries"], [])


if __name__ == "__main__":
    unittest.main()
