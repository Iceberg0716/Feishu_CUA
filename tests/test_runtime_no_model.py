"""Runtime smoke test without calling external VLM APIs."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cua_lark import orchestrator as orch_module
from cua_lark.config import config
from cua_lark.execution.action_types import ActionChunk
from cua_lark.orchestrator import Orchestrator


def _fake_capture_factory(tmpdir: Path):
    counter = {"value": 0}

    def _fake_capture(role: str, instruction: str = "", monitor_index: int = 1):
        counter["value"] += 1
        img = Image.new("RGB", (1280, 720), color=(240, 240, 240))
        path = tmpdir / f"{counter['value']:04d}_{role}.png"
        img.save(path)
        return img, str(path)

    return _fake_capture


def _make_common_patches(fake_analyze_screen, fake_execute):
    return (
        patch.object(orch_module, "wait_for_user_idle", lambda *args, **kwargs: None),
        patch.object(orch_module, "ensure_target_app_focused", return_value=SimpleNamespace(recovered=True, reason="ok")),
        patch.object(orch_module, "recover_to_known_state", return_value=SimpleNamespace(recovered=True, reason="recovered")),
        patch.object(orch_module, "classify_state", return_value=SimpleNamespace(app_in_view=True, state="messages", confidence=0.99, reason="ok")),
        patch.object(orch_module, "analyze_screen", side_effect=fake_analyze_screen),
        patch.object(orch_module, "verify_step", return_value=SimpleNamespace(passed=True, reason="fake pass")),
        patch.object(orch_module, "confirm_click_target", return_value=SimpleNamespace(element_name="fake_element", is_target=True, confidence=0.9, raw_response="{}")),
        patch.object(orch_module, "execute", side_effect=fake_execute),
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        trace_file = tmpdir / "trace.jsonl"
        old_trace = config.trace_file
        config.trace_file = str(trace_file)

        try:
            # Case 1: region retry + refined localization
            executed_actions_case1: list[str] = []
            analyze_calls_case1: list[str] = []

            def fake_execute_case1(action):
                if isinstance(action, ActionChunk):
                    executed_actions_case1.append("ActionChunk")
                    for sub_action in action.actions:
                        executed_actions_case1.append(type(sub_action).__name__)
                else:
                    executed_actions_case1.append(type(action).__name__)

            def fake_analyze_screen_case1(_image, _instruction, region_hint=""):
                analyze_calls_case1.append(region_hint)
                if region_hint == "left_nav":
                    raise RuntimeError("fake region miss")
                return SimpleNamespace(
                    thought="fake",
                    action="chunk",
                    params={},
                    confidence=0.95,
                    raw_response=json.dumps(
                        {
                            "goal": "open messages and click target",
                            "actions": [
                                {"action": "wait", "params": {"ms": 100}},
                                {"action": "click", "params": {"x": 100, "y": 120}},
                            ],
                            "verify_each_step": True,
                            "stop_on_failure": True,
                            "confidence": 0.95,
                        }
                    ),
                )

            patches = _make_common_patches(fake_analyze_screen_case1, fake_execute_case1)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
                orch = Orchestrator()
                orch.screenshot.capture = _fake_capture_factory(tmpdir)
                orch.screenshot.crop_foreground_window = lambda image: (image, None)
                result = orch.run_step("点击飞书左侧导航栏中的聊天入口-非常规")

            assert result.verdict_passed is True
            assert result.page_state == "messages"
            assert result.region_hint in {"left_nav", "top_bar", "content", "content_refined", "refined_patch", "full_window"}
            assert executed_actions_case1 in (
                ["ActionChunk", "WaitAction", "ClickAction"],
                ["WaitAction", "ClickAction"],
            )
            # full_window 模式下首个 VLM 调用即为 full_window，不再需要 left_nav→content 回退
            assert analyze_calls_case1[0] in {"full_window", "left_nav"}

            # Case 2: knowledge template hit should skip VLM
            executed_actions_case2: list[str] = []
            analyze_calls_case2: list[str] = []

            def fake_execute_case2(action):
                if isinstance(action, ActionChunk):
                    executed_actions_case2.append("ActionChunk")
                    for sub_action in action.actions:
                        executed_actions_case2.append(type(sub_action).__name__)
                else:
                    executed_actions_case2.append(type(action).__name__)

            def fake_analyze_screen_case2(_image, _instruction, region_hint=""):
                analyze_calls_case2.append(region_hint)
                raise RuntimeError("template path should skip analyze_screen")

            patches = _make_common_patches(fake_analyze_screen_case2, fake_execute_case2)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
                orch = Orchestrator()
                orch.screenshot.capture = _fake_capture_factory(tmpdir)
                orch.screenshot.crop_foreground_window = lambda image: (image, None)
                result = orch.run_step("打开消息模块")

            assert result.verdict_passed is True
            assert result.region_hint == "knowledge_template"
            assert analyze_calls_case2 == []
            assert executed_actions_case2 in (
                ["ActionChunk", "HotkeyAction", "WaitAction"],
                ["HotkeyAction", "WaitAction"],
            )
            assert trace_file.exists()

            lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 2
            record = json.loads(lines[-1])
            assert record["verdict"]["passed"] is True
            assert record["action"]["_type"] == "ActionChunk"

            # Case 3: parameterized template hit should fill slot and skip VLM
            executed_actions_case3: list[str] = []
            analyze_calls_case3: list[str] = []

            def fake_execute_case3(action):
                if isinstance(action, ActionChunk):
                    executed_actions_case3.append("ActionChunk")
                    for sub_action in action.actions:
                        executed_actions_case3.append(type(sub_action).__name__)
                else:
                    executed_actions_case3.append(type(action).__name__)

            def fake_analyze_screen_case3(_image, _instruction, region_hint=""):
                analyze_calls_case3.append(region_hint)
                raise RuntimeError("parameterized template path should skip analyze_screen")

            patches = _make_common_patches(fake_analyze_screen_case3, fake_execute_case3)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
                orch = Orchestrator()
                orch.screenshot.capture = _fake_capture_factory(tmpdir)
                orch.screenshot.crop_foreground_window = lambda image: (image, None)
                result = orch.run_step("在搜索框中输入 测试群")

            assert result.verdict_passed is True
            assert result.region_hint == "knowledge_template"
            assert analyze_calls_case3 == []
            assert executed_actions_case3 in (
                ["ActionChunk", "HotkeyAction", "WaitAction", "TypeAction"],
                ["HotkeyAction", "WaitAction", "TypeAction"],
            )

            # Case 4: template precondition miss should fall back to VLM
            executed_actions_case4: list[str] = []
            analyze_calls_case4: list[str] = []

            def fake_execute_case4(action):
                if isinstance(action, ActionChunk):
                    executed_actions_case4.append("ActionChunk")
                    for sub_action in action.actions:
                        executed_actions_case4.append(type(sub_action).__name__)
                else:
                    executed_actions_case4.append(type(action).__name__)

            def fake_analyze_screen_case4(_image, _instruction, region_hint=""):
                analyze_calls_case4.append(region_hint)
                return SimpleNamespace(
                    thought="fake",
                    action="chunk",
                    params={},
                    confidence=0.91,
                    raw_response=json.dumps(
                        {
                            "goal": "fallback click target",
                            "actions": [
                                {"action": "click", "params": {"x": 80, "y": 90}}
                            ],
                            "verify_each_step": False,
                            "stop_on_failure": True,
                            "confidence": 0.91,
                        }
                    ),
                )

            patches = _make_common_patches(fake_analyze_screen_case4, fake_execute_case4)
            with patches[0], patches[1], patches[2], patches[4], patches[5], patches[6], patches[7]:
                classify_sequence = iter(
                    [
                        SimpleNamespace(app_in_view=False, state="messages", confidence=0.99, reason="blocked"),
                        SimpleNamespace(app_in_view=False, state="messages", confidence=0.99, reason="blocked_after_recover"),
                        SimpleNamespace(app_in_view=True, state="messages", confidence=0.99, reason="verify_ok"),
                    ]
                )
                with patch.object(orch_module, "classify_state", side_effect=lambda *_args, **_kwargs: next(classify_sequence)):
                    orch = Orchestrator()
                    orch.screenshot.capture = _fake_capture_factory(tmpdir)
                    orch.screenshot.crop_foreground_window = lambda image: (image, None)
                    result = orch.run_step("打开消息模块")

            assert result.verdict_passed is True
            assert result.region_hint in {"content", "top_bar", "left_nav", "content_refined", "refined_patch", "full_window"}
            assert analyze_calls_case4 != []

            # Case 5: template postcondition fail should recover and fall back to VLM
            executed_actions_case5: list[str] = []
            analyze_calls_case5: list[str] = []

            def fake_execute_case5(action):
                if isinstance(action, ActionChunk):
                    executed_actions_case5.append("ActionChunk")
                    for sub_action in action.actions:
                        executed_actions_case5.append(type(sub_action).__name__)
                else:
                    executed_actions_case5.append(type(action).__name__)

            def fake_analyze_screen_case5(_image, _instruction, region_hint=""):
                analyze_calls_case5.append(region_hint)
                return SimpleNamespace(
                    thought="fake",
                    action="chunk",
                    params={},
                    confidence=0.93,
                    raw_response=json.dumps(
                        {
                            "goal": "fallback after template failure",
                            "actions": [
                                {"action": "wait", "params": {"ms": 50}},
                                {"action": "click", "params": {"x": 160, "y": 140}}
                            ],
                            "verify_each_step": True,
                            "stop_on_failure": True,
                            "confidence": 0.93,
                        }
                    ),
                )

            classify_sequence = iter(
                [
                    SimpleNamespace(app_in_view=True, state="calendar", confidence=0.99, reason="before template"),
                    SimpleNamespace(app_in_view=True, state="calendar", confidence=0.99, reason="template post app"),
                    SimpleNamespace(app_in_view=True, state="calendar", confidence=0.99, reason="template post state"),
                    SimpleNamespace(app_in_view=True, state="messages", confidence=0.99, reason="fallback replanned"),
                    SimpleNamespace(app_in_view=True, state="messages", confidence=0.99, reason="verify foreground"),
                ]
            )

            patches = _make_common_patches(fake_analyze_screen_case5, fake_execute_case5)
            with patches[0], patches[1], patches[2], patches[4], patches[5], patches[6], patches[7]:
                with patch.object(orch_module, "classify_state", side_effect=lambda *_args, **_kwargs: next(classify_sequence)):
                    orch = Orchestrator()
                    orch.screenshot.capture = _fake_capture_factory(tmpdir)
                    orch.screenshot.crop_foreground_window = lambda image: (image, None)
                    result = orch.run_step("打开消息模块")

            assert result.verdict_passed is True
            assert result.region_hint in {"content", "top_bar", "left_nav", "content_refined", "refined_patch", "full_window"}
            assert analyze_calls_case5 != []
            assert "HotkeyAction" in executed_actions_case5
            assert "ClickAction" in executed_actions_case5
            lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 5

            print("NO_MODEL_RUNTIME_TEST: PASS")
            print(f"trace_file={trace_file}")
            print(f"case1_actions={executed_actions_case1}")
            print(f"case1_analyze_calls={analyze_calls_case1}")
            print(f"case2_actions={executed_actions_case2}")
            print(f"case2_analyze_calls={analyze_calls_case2}")
            print(f"case3_actions={executed_actions_case3}")
            print(f"case3_analyze_calls={analyze_calls_case3}")
            print(f"case4_actions={executed_actions_case4}")
            print(f"case4_analyze_calls={analyze_calls_case4}")
            print(f"case5_actions={executed_actions_case5}")
            print(f"case5_analyze_calls={analyze_calls_case5}")
            return 0
        finally:
            config.trace_file = old_trace


if __name__ == "__main__":
    raise SystemExit(main())
