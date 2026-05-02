"""Main agent loop: screenshot -> state -> localize -> execute -> verify -> record."""

import re
import time
from dataclasses import dataclass

from PIL import Image

from .config import config
from .execution.action_types import (
    Action,
    ActionChunk,
    ClickAction,
    DoubleClickAction,
    DragAction,
    MouseMoveAction,
    ScrollAction,
)
from .execution.input_guard import wait_for_user_idle
from .execution.operator import execute
from .execution.parser import _parse_atomic_action, parse_action
from .execution.recovery import ensure_target_app_focused, recover_to_known_state
from .execution.window_manager import WindowBounds
from .knowledge_base import load_app_knowledge
from .perception.screenshot import Screenshot
from .perception.state_classifier import classify_state
from .perception.vlm_client import analyze_screen, confirm_click_target
from .recorder import Recorder
from .verification.verifier import verify as verify_step


VLM_MAX_WIDTH = 1280  # VLM 推荐输入宽度，超过此值会等比缩放


def _calc_vlm_size(native_width: int) -> int:
    """计算传给 VLM 的图像宽度：超过1920px的屏幕缩放至1280px。"""
    return VLM_MAX_WIDTH if native_width > 1920 else native_width


def _resize_for_vlm(img: Image.Image, target_width: int) -> tuple[Image.Image, float]:
    """将图像缩放到目标宽度，返回缩放后的图像和缩放比例。"""
    w, h = img.size
    if w <= target_width:
        return img, 1.0
    scale = target_width / w
    new_h = int(h * scale)
    return img.resize((target_width, new_h), Image.LANCZOS), scale


def _scale_atomic(action: Action, factor: float) -> Action:
    """将单个原子动作的坐标按比例缩放（用于VLM缩放→原始屏幕转换）。"""
    if factor == 1.0:
        return action
    if isinstance(action, (ClickAction, DoubleClickAction, MouseMoveAction)):
        action.x = round(action.x * factor)
        action.y = round(action.y * factor)
    elif isinstance(action, DragAction):
        action.start_x = round(action.start_x * factor)
        action.start_y = round(action.start_y * factor)
        action.end_x = round(action.end_x * factor)
        action.end_y = round(action.end_y * factor)
    elif isinstance(action, ScrollAction) and (action.x or action.y):
        action.x = round(action.x * factor)
        action.y = round(action.y * factor)
    return action


def _scale_action_coords(action: Action, factor: float) -> Action:
    """将动作的坐标从 VLM 空间还原到原始屏幕空间。"""
    if isinstance(action, ActionChunk):
        action.actions = [_scale_atomic(sub_action, factor) for sub_action in action.actions]
        return action
    return _scale_atomic(action, factor)


def _offset_action_coords(action: Action, offset_x: int, offset_y: int) -> Action:
    """将窗口相对坐标加上窗口左上角屏幕偏移量，转换为屏幕绝对坐标。

    Hotkey/Type/Wait 等不涉及坐标的动作不受影响。
    """
    if isinstance(action, ActionChunk):
        for sub_action in action.actions:
            _offset_action_coords(sub_action, offset_x, offset_y)
        return action
    if isinstance(action, (ClickAction, DoubleClickAction, MouseMoveAction)):
        action.x += offset_x
        action.y += offset_y
    elif isinstance(action, DragAction):
        action.start_x += offset_x
        action.start_y += offset_y
        action.end_x += offset_x
        action.end_y += offset_y
    elif isinstance(action, ScrollAction) and (action.x or action.y):
        action.x += offset_x
        action.y += offset_y
    return action


@dataclass
class StepResult:
    """单步执行结果，包含操作、验证、截图路径和耗时等完整信息。"""
    instruction: str
    action: Action | None
    verdict_passed: bool
    verdict_reason: str
    before_path: str
    after_path: str
    vlm_raw: str
    elapsed_ms: float
    page_state: str
    recovery_reason: str
    attempts: int
    region_hint: str


class Orchestrator:
    """执行编排器，负责将用户指令转化为完整的感知-定位-执行-验证流水线。

    核心流程 (run_step):
      1. 等待用户空闲 → 聚焦目标应用
      2. 截图 → 裁剪前景窗口 → 状态分类
      3. 尝试知识库模板匹配，失败则走 VLM 区域定位
      4. 执行动作 → 验证结果 → 记录轨迹
      5. 失败时自动恢复并重试
    """

    def __init__(self):
        """初始化：加载应用知识库、创建截图会话和轨迹记录器。"""
        self.knowledge = load_app_knowledge(config.app_knowledge_path)
        self.screenshot = Screenshot(
            output_dir=config.screenshot_dir,
            prefix=config.screenshot_prefix,
        )
        self.recorder = Recorder()

    def _instruction_region_key(self, instruction: str) -> str | None:
        """根据指令关键词推断应优先搜索的界面区域。"""
        lowered = instruction.lower()
        if any(token in instruction for token in ("左侧", "导航", "消息", "日历", "文档", "邮箱")):
            return "navigation"
        if any(token in lowered for token in ("search", "toolbar")) or "搜索" in instruction:
            return "search"
        return None

    def _extract_template_slots(self, template: dict[str, object], instruction: str) -> dict[str, str] | None:
        """从指令中提取模板需要的参数槽位，如"输入 测试群" → {"text": "测试群"}。

        任一槽位匹配失败则返回 None，表示该模板不适用于当前指令。
        """
        slots = template.get("slots", {})
        if not slots:
            return {}
        extracted: dict[str, str] = {}
        for slot_name, slot_config in slots.items():
            pattern = slot_config.get("pattern", "")
            if not pattern:
                return None
            match = re.search(pattern, instruction)
            if not match:
                return None
            extracted[slot_name] = match.group(1).strip()
        return extracted

    def _apply_slots(self, value, slots: dict[str, str]):
        """递归替换模板中的占位符 {{slot_name}} 为实际参数值。"""
        if isinstance(value, str):
            for slot_name, slot_value in slots.items():
                value = value.replace(f"{{{{{slot_name}}}}}", slot_value)
            return value
        if isinstance(value, list):
            return [self._apply_slots(item, slots) for item in value]
        if isinstance(value, dict):
            return {k: self._apply_slots(v, slots) for k, v in value.items()}
        return value

    def _template_preconditions_met(
        self,
        template: dict[str, object],
        page_state: str,
        app_in_view: bool,
    ) -> bool:
        """检查模板前置条件是否满足（应用是否在前台、页面状态是否匹配）。"""
        preconditions = template.get("preconditions", {})
        if preconditions.get("app_in_view") is True and not app_in_view:
            return False
        state_in = preconditions.get("state_in", [])
        if state_in and page_state not in state_in:
            return False
        state_not_in = preconditions.get("state_not_in", [])
        if state_not_in and page_state in state_not_in:
            return False
        return True

    def _template_postconditions_met(
        self,
        template: dict[str, object],
        before_img: Image.Image,
        after_img: Image.Image,
        slots: dict[str, str],
    ) -> tuple[bool, str]:
        """验证模板执行后置条件是否满足（状态检查 + VLM 语义对比）。"""
        postconditions = self._apply_slots(template.get("postconditions", {}), slots)
        if not postconditions:
            return True, ""
        if postconditions.get("app_in_view") is True:
            state_after = classify_state(after_img, self.knowledge)
            if not state_after.app_in_view:
                return False, "target app not in view after template execution"
        state_in = postconditions.get("state_in", [])
        if state_in:
            state_after = classify_state(after_img, self.knowledge)
            if state_after.state not in state_in:
                return False, f"page state {state_after.state} not in {state_in}"
        verify_instruction = postconditions.get("verify_instruction", "")
        if verify_instruction:
            verdict = verify_step(before_img, after_img, verify_instruction)
            if not verdict.passed:
                return False, verdict.reason
        return True, ""

    def _template_action_for_instruction(
        self,
        instruction: str,
        page_state: str,
        app_in_view: bool,
    ) -> tuple[Action | None, str, dict[str, object] | None, dict[str, str]]:
        """尝试从知识库模板中匹配指令并生成动作。

        Returns:
            (action, source_tag, template_meta, slots) — action 为 None 表示未命中模板。
        """
        lowered = instruction.lower()
        for template in self.knowledge.task_templates:
            allowed_states = template.get("allowed_states", [])
            if allowed_states and page_state not in allowed_states:
                continue
            if not self._template_preconditions_met(template, page_state, app_in_view):
                continue
            match_any = template.get("match_any", [])
            if not any(keyword.lower() in lowered for keyword in match_any):
                continue
            slots = self._extract_template_slots(template, instruction)
            if slots is None:
                continue
            action_payload = template.get("action", {})
            action_payload = self._apply_slots(action_payload, slots or {})
            actions = []
            for item in action_payload.get("actions", []):
                actions.append(_parse_atomic_action(item.get("action", ""), item.get("params", {}), 4000, 4000))
            action = ActionChunk(
                goal=action_payload.get("goal", template.get("name", "")),
                actions=actions,
                verify_each_step=bool(action_payload.get("verify_each_step", False)),
                stop_on_failure=bool(action_payload.get("stop_on_failure", True)),
            )
            return action, f"template:{template.get('name', 'unknown')}", template, slots or {}
        return None, "", None, {}

    def _select_region_order(self, instruction: str, page_state: str) -> list[str]:
        """根据指令和页面状态确定界面区域的搜索优先级顺序。"""
        instruction_key = self._instruction_region_key(instruction)
        if instruction_key and instruction_key in self.knowledge.region_preferences:
            return self.knowledge.region_preferences[instruction_key]
        if page_state in self.knowledge.region_preferences:
            return self.knowledge.region_preferences[page_state]
        return self.knowledge.region_preferences.get("default", ["content", "top_bar", "left_nav"])

    def _region_candidates(self, image: Image.Image, region_order: list[str]) -> list[tuple[Image.Image, str]]:
        """按优先级顺序裁剪界面各区域子图，保证 content/top_bar/left_nav 兜底。"""
        zones = self.screenshot.split_zones(image)
        zone_map = {
            "left_nav": self.screenshot.crop_zone(image, zones.left_nav),
            "top_bar": self.screenshot.crop_zone(image, zones.top_bar),
            "content": self.screenshot.crop_zone(image, zones.content),
        }
        deduped = []
        for name in region_order:
            if name in zone_map and name not in deduped:
                deduped.append(name)
        for fallback in ("content", "top_bar", "left_nav"):
            if fallback not in deduped:
                deduped.append(fallback)
        return [(zone_map[name], name) for name in deduped]

    def _validation_policy_for_action(self, action: Action) -> dict[str, bool]:
        """根据动作类型查询对应的验证策略（是否逐步验证、失败是否停止等）。"""
        if isinstance(action, ActionChunk):
            return self.knowledge.validation_policies.get("chunk", self.knowledge.validation_policies.get("default", {}))
        action_name = type(action).__name__.replace("Action", "").lower()
        return self.knowledge.validation_policies.get(action_name, self.knowledge.validation_policies.get("default", {}))

    def _localize_action(self, image: Image.Image, instruction: str, region_hint: str) -> tuple[Action, str, float]:
        """将区域截图发送给 VLM 进行定位分析，返回解析后的动作、原始响应和置信度。"""
        vlm_target = _calc_vlm_size(image.width)
        vlm_img, scale = _resize_for_vlm(image, vlm_target)
        vlm_resp = analyze_screen(vlm_img, instruction, region_hint=region_hint)
        vlm_w, vlm_h = vlm_img.size
        action = parse_action(vlm_resp.raw_response, vlm_w, vlm_h)
        action = _scale_action_coords(action, 1.0 / scale)
        return action, vlm_resp.raw_response, vlm_resp.confidence

    def _refine_region(self, image: Image.Image, coarse_action: Action) -> tuple[Image.Image, str]:
        """根据粗定位动作裁剪目标附近区域，用于二次精细 VLM 定位。"""
        if isinstance(coarse_action, ActionChunk):
            return image, "content_refined"
        if isinstance(coarse_action, (ClickAction, DoubleClickAction, MouseMoveAction)):
            x = getattr(coarse_action, "x")
            y = getattr(coarse_action, "y")
            width, height = image.size
            pad_x = max(80, width // 6)
            pad_y = max(80, height // 6)
            left = max(0, x - pad_x)
            top = max(0, y - pad_y)
            right = min(width, x + pad_x)
            bottom = min(height, y + pad_y)
            return image.crop((left, top, right, bottom)), "refined_patch"
        return image, "content_refined"

    def _execute_action(self, action: Action, instruction: str, before_img: Image.Image,
                        is_template: bool = False) -> tuple[bool, str]:
        """执行动作并按策略验证：单步动作直接执行，Chunk 模式支持逐步验证。

        Args:
            is_template: 若为 True，跳过验证策略覆盖（模板已显式配置验证参数）。
        """
        policy = self._validation_policy_for_action(action)
        # 仅 VLM 生成的动作需要策略覆盖；模板动作自带完整的 verify_each_step/stop_on_failure 配置
        if isinstance(action, ActionChunk) and not is_template:
            action.verify_each_step = bool(policy.get("verify_each_step", action.verify_each_step))
            action.stop_on_failure = bool(policy.get("stop_on_failure", action.stop_on_failure))

        if not isinstance(action, ActionChunk) or not action.verify_each_step:
            execute(action)
            return True, ""

        current_before = before_img
        for index, sub_action in enumerate(action.actions, start=1):
            execute(sub_action)
            wait_for_user_idle(
                idle_timeout_s=min(config.input_idle_timeout_s, config.post_action_settle_timeout_s),
                poll_interval_s=config.post_action_settle_poll_s,
            )
            after_img, _ = self.screenshot.capture(f"chunk_after_{index}", instruction=instruction)
            after_window, _ = self.screenshot.crop_foreground_window(after_img)
            verdict = verify_step(current_before, after_window, f"{instruction} [chunk step {index}]")
            if not verdict.passed and action.stop_on_failure:
                return False, f"chunk step {index} failed: {verdict.reason}"
            current_before = after_window
        return True, ""

    def _confirm_click_target(self, full_screen_img: Image.Image, action: Action, instruction: str) -> tuple[bool, str]:
        """点击前目标确认：裁剪目标点周围 60×60 区域，发送给 VLM 确认十字准星处是否为预期元素。

        Args:
            full_screen_img: 全屏截图（用于裁剪，坐标已是屏幕绝对值）
            action: 待执行的点击动作
            instruction: 用户指令

        Returns:
            (confirmed, reason)
        """
        if isinstance(action, ActionChunk):
            # 确认动作块中的第一个点击子动作
            for sub_action in action.actions:
                if isinstance(sub_action, (ClickAction, DoubleClickAction)):
                    return self._confirm_click_target(full_screen_img, sub_action, instruction)
            return True, ""
        if not isinstance(action, (ClickAction, DoubleClickAction)):
            return True, ""
        x, y = action.x, action.y
        img_w, img_h = full_screen_img.size
        pad = 40
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(img_w, x + pad)
        bottom = min(img_h, y + pad)
        patch = full_screen_img.crop((left, top, right, bottom))
        result = confirm_click_target(patch, instruction)
        if result.is_target:
            return True, ""
        return False, f"preclick confirmation: expected target, but VLM identified '{result.element_name}' (conf={result.confidence})"

    def _plan_vlm_action(
        self,
        window_img: Image.Image,
        instruction: str,
        page_state: str,
    ) -> tuple[Action, str, str]:
        """VLM 动作规划。

        两种模式（由 config.localization_mode 控制）:
          - full_window: 整窗口截图一次性分析（默认，减少裁剪偏差）。
          - region: 按区域优先级尝试定位，粗定位+细化定位两步走。
        """
        if config.localization_mode == "full_window":
            try:
                action, vlm_raw, conf = self._localize_action(window_img, instruction, "full_window")
                if conf >= 0.5:
                    return action, vlm_raw, "full_window"
            except Exception as exc:
                pass
            # full_window 失败则回退到 region 模式
            print(f"[PLAN] full_window localization failed, falling back to region mode")

        region_order = self._select_region_order(instruction, page_state)
        region_error = ""
        for region_img, candidate_region_hint in self._region_candidates(window_img, region_order):
            try:
                coarse_action, coarse_raw, coarse_conf = self._localize_action(region_img, instruction, candidate_region_hint)
                refined_img, refined_hint = self._refine_region(region_img, coarse_action)
                action = coarse_action
                vlm_raw = coarse_raw
                region_hint = candidate_region_hint
                if refined_hint != candidate_region_hint:
                    refined_action, refined_raw, refined_conf = self._localize_action(refined_img, instruction, refined_hint)
                    if refined_conf >= coarse_conf:
                        action = refined_action
                        vlm_raw = refined_raw
                        region_hint = refined_hint
                return action, vlm_raw, region_hint
            except Exception as exc:
                region_error = str(exc)
                continue
        raise RuntimeError(f"鎵€鏈夊垎鍖哄畾浣嶅潎澶辫触: {region_error}")

    def _ensure_verifiable_foreground(self, instruction: str) -> tuple[Image.Image, str, object]:
        """确保目标应用在前台且可验证：聚焦→等待空闲→截图→分类状态。"""
        focus_result = ensure_target_app_focused(self.knowledge)
        if not focus_result.recovered:
            raise RuntimeError(f"verification focus failed: {focus_result.reason}")
        wait_for_user_idle(
            idle_timeout_s=min(config.input_idle_timeout_s, config.post_action_settle_timeout_s),
            poll_interval_s=config.post_action_settle_poll_s,
        )
        verify_img, verify_path = self.screenshot.capture("verify_foreground", instruction=instruction)
        verify_window_img, _ = self.screenshot.crop_foreground_window(verify_img)
        verify_state = classify_state(verify_window_img, self.knowledge)
        return verify_window_img, verify_path, verify_state

    def _run_step_once(self, instruction: str) -> StepResult:
        """执行单步指令的完整流水线（不含重试逻辑）。

        流程: 聚焦 → 截图 → 状态分类 → (恢复) → 模板/VLM定位 → 执行 → 验证 → 记录
        """
        t0 = time.time()
        recovery_reason = ""
        cleanup_paths: list[str] = []

        wait_for_user_idle(config.input_idle_timeout_s, config.input_poll_interval_s)
        focus_result = ensure_target_app_focused(self.knowledge)
        if not focus_result.recovered:
            raise RuntimeError(f"无法聚焦目标应用: {focus_result.reason}")

        before_img, before_path = self.screenshot.capture("before", instruction=instruction)
        cleanup_paths.append(before_path)
        window_img, window_bounds = self.screenshot.crop_foreground_window(before_img)
        page_state = classify_state(window_img, self.knowledge)
        print(f"[STATE] app_in_view={page_state.app_in_view} state={page_state.state} conf={page_state.confidence}")
        if not page_state.app_in_view or page_state.state == "unknown":
            recovery = recover_to_known_state(
                "初始页面未知或目标应用不在视图中",
                self.knowledge,
                current_state=page_state.state,
            )
            recovery_reason = recovery.reason
            if not recovery.recovered:
                raise RuntimeError(f"恢复失败: {recovery.reason}")
            wait_for_user_idle(config.input_idle_timeout_s, config.input_poll_interval_s)
            before_img, before_path = self.screenshot.capture("before_recovered", instruction=instruction)
            cleanup_paths.append(before_path)
            window_img, window_bounds = self.screenshot.crop_foreground_window(before_img)
            page_state = classify_state(window_img, self.knowledge)

        template_action, template_raw, template_meta, template_slots = self._template_action_for_instruction(
            instruction,
            page_state.state,
            page_state.app_in_view,
        )
        action = template_action
        vlm_raw = template_raw
        region_hint = "content"
        if action is None:
            action, vlm_raw, region_hint = self._plan_vlm_action(window_img, instruction, page_state.state)
        else:
            region_hint = "knowledge_template"

        print(f"[VLM] region={region_hint} action={type(action).__name__}")

        # 将窗口相对坐标转换为屏幕绝对坐标（PyAutoGUI 需要屏幕坐标）
        if window_bounds is not None:
            _offset_action_coords(action, window_bounds.left, window_bounds.top)

        # 点击前目标确认：裁剪目标点周围区域发送给 VLM 确认目标是否匹配
        execute_ok = True
        execute_reason = ""
        if config.preclick_confirmation and not template_action:
            execute_ok, execute_reason = self._confirm_click_target(before_img, action, instruction)
            if not execute_ok:
                print(f"[CONFIRM-FAIL] {execute_reason}")

        if execute_ok:
            execute_ok, execute_reason = self._execute_action(action, instruction, window_img,
                                                               is_template=template_action is not None)
        if not execute_ok:
            recovery_reason = execute_reason

        wait_for_user_idle(
            idle_timeout_s=min(config.input_idle_timeout_s, config.post_action_settle_timeout_s),
            poll_interval_s=config.post_action_settle_poll_s,
        )

        after_img, after_path = self.screenshot.capture("after", instruction=instruction)
        cleanup_paths.append(after_path)
        after_window_img, _ = self.screenshot.crop_foreground_window(after_img)
        if template_meta is not None:
            template_ok, template_reason = self._template_postconditions_met(
                template_meta,
                window_img,
                after_window_img,
                template_slots,
            )
            if not template_ok:
                recovery = recover_to_known_state(
                    f"模板后置条件失败: {template_reason}",
                    self.knowledge,
                    current_state=page_state.state,
                )
                recovery_reason = recovery.reason if recovery.recovered else template_reason
                wait_for_user_idle(config.input_idle_timeout_s, config.input_poll_interval_s)
                before_img, before_path = self.screenshot.capture("before_template_fallback", instruction=instruction)
                cleanup_paths.append(before_path)
                window_img, window_bounds = self.screenshot.crop_foreground_window(before_img)
                page_state = classify_state(window_img, self.knowledge)
                action, vlm_raw, region_hint = self._plan_vlm_action(window_img, instruction, page_state.state)
                print(f"[TEMPLATE-FALLBACK] reason={template_reason} region={region_hint}")
                # 模板回退的 VLM 动作同样需要窗口偏移补偿
                if window_bounds is not None:
                    _offset_action_coords(action, window_bounds.left, window_bounds.top)
                # 回退路径也需要点击前确认，因 VLM 在模板失败后的定位可能不准
                if config.preclick_confirmation:
                    execute_ok, execute_reason = self._confirm_click_target(before_img, action, instruction)
                    if not execute_ok:
                        print(f"[CONFIRM-FAIL] {execute_reason}")
                if execute_ok:
                    execute_ok, execute_reason = self._execute_action(action, instruction, window_img)
                if not execute_ok:
                    recovery_reason = execute_reason
                wait_for_user_idle(
                    idle_timeout_s=min(config.input_idle_timeout_s, config.post_action_settle_timeout_s),
                    poll_interval_s=config.post_action_settle_poll_s,
                )
                after_img, after_path = self.screenshot.capture("after_template_fallback", instruction=instruction)
                cleanup_paths.append(after_path)
                after_window_img, _ = self.screenshot.crop_foreground_window(after_img)
        verify_after_action = bool(self._validation_policy_for_action(action).get("verify_after_action", True))
        if verify_after_action:
            verify_window_img, verify_path, verify_state = self._ensure_verifiable_foreground(instruction)
            cleanup_paths.append(verify_path)
            if not verify_state.app_in_view:
                verdict = type(
                    "Verdict",
                    (),
                    {
                        "passed": False,
                        "reason": f"verification blocked: target app not in foreground view (state={verify_state.state})",
                    },
                )()
            else:
                verdict = verify_step(window_img, verify_window_img, instruction)
            if not verdict.passed:
                recovery = recover_to_known_state(
                    f"验证失败: {verdict.reason}",
                    self.knowledge,
                    current_state=page_state.state,
                )
                recovery_reason = recovery.reason if recovery.recovered else f"{recovery_reason}; {recovery.reason}".strip("; ")
        else:
            verdict = type("Verdict", (), {"passed": True, "reason": "verification skipped by policy"})()

        self.recorder.record(
            instruction=instruction,
            vlm_raw=vlm_raw,
            action=action,
            verdict_passed=verdict.passed,
            verdict_reason=verdict.reason,
            before_path=before_path,
            after_path=after_path,
        )

        keep_screenshots = (
            (verdict.passed and config.screenshot_keep_passed)
            or ((not verdict.passed) and config.screenshot_keep_failed)
        )
        self.screenshot.mark_step(
            before_path,
            after_path,
            keep_screenshots,
            "PASS" if verdict.passed else "FAIL",
            extra_paths=cleanup_paths,
        )
        self.screenshot.cleanup_sessions(
            config.screenshot_keep_latest_sessions,
            config.screenshot_keep_max_age_hours,
        )

        return StepResult(
            instruction=instruction,
            action=action,
            verdict_passed=verdict.passed,
            verdict_reason=verdict.reason,
            before_path=before_path,
            after_path=after_path,
            vlm_raw=vlm_raw,
            elapsed_ms=(time.time() - t0) * 1000,
            page_state=page_state.state,
            recovery_reason=recovery_reason,
            attempts=1,
            region_hint=region_hint,
        )

    def run_step(self, instruction: str) -> StepResult:
        """执行单步指令，支持失败重试和异常恢复。

        最多重试 config.recovery_max_attempts 次，每次失败后先执行恢复序列再重试。
        """
        last_result: StepResult | None = None
        last_error: Exception | None = None
        for attempt in range(1, config.recovery_max_attempts + 1):
            try:
                result = self._run_step_once(instruction)
                result.attempts = attempt
                last_result = result
                if result.verdict_passed:
                    return result
                if attempt < config.recovery_max_attempts:
                    print(f"[RETRY] attempt={attempt} recovery={result.recovery_reason or 'none'}")
                    continue
                return result
            except Exception as exc:
                last_error = exc
                if attempt < config.recovery_max_attempts:
                    recovery = recover_to_known_state(
                        f"异常重试前恢复: {exc}",
                        self.knowledge,
                        current_state="unknown",
                    )
                    print(f"[RETRY-ERROR] attempt={attempt} error={exc} recovery={recovery.reason}")
                    continue
                raise
        if last_error is not None:
            raise last_error
        if last_result is not None:
            return last_result
        raise RuntimeError("未能执行任务")
