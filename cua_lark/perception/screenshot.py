"""Cross-platform screen capture using mss with session-aware retention."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import mss
from PIL import Image

from ..execution.window_manager import WindowBounds, get_foreground_window_bounds


@dataclass
class ScreenZones:
    """界面功能区域划分：左侧导航栏、顶部工具栏、中央内容区。"""
    left_nav: tuple[int, int, int, int]
    top_bar: tuple[int, int, int, int]
    content: tuple[int, int, int, int]


class Screenshot:
    """截图会话管理器，负责截图、存盘、裁剪、清理整个生命周期。

    每次实例化创建独立的 session_id 子目录。
    """

    def __init__(self, output_dir: str = "logs/screenshots", prefix: str = "step_"):
        self.output_dir = Path(output_dir)
        self.prefix = prefix
        # 按时间戳创建唯一会话目录
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / self.session_id
        self.counter = 0
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.session_dir / "index.json"
        self._entries: list[dict] = []

    def capture(self, role: str, instruction: str = "", monitor_index: int = 1) -> tuple[Image.Image, str]:
        """使用 mss 截取指定显示器的全屏并保存为 PNG。

        Returns:
            (PIL Image, 文件路径)
        """
        with mss.mss() as sct:
            monitor = sct.monitors[monitor_index]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        self.counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{self.prefix}{self.counter:04d}_{role}_{timestamp}.png"
        filepath = self.session_dir / filename
        img.save(filepath, "PNG")
        self._entries.append(
            {
                "step": self.counter,
                "role": role,
                "instruction": instruction,
                "path": str(filepath),
                "timestamp": timestamp,
            }
        )
        self._write_index()
        return img, str(filepath)

    def crop_foreground_window(self, image: Image.Image) -> tuple[Image.Image, WindowBounds | None]:
        """裁剪图像到前台窗口的边界范围，裁剪失败或窗口过小返回原图。

        VLM API 要求输入图像各维度至少 10px，因此裁剪结果 < 20px 时回退到全屏。
        """
        bounds = get_foreground_window_bounds()
        if bounds is None:
            return image, None
        width, height = image.size
        left = max(0, min(bounds.left, width))
        top = max(0, min(bounds.top, height))
        right = max(left + 1, min(bounds.right, width))
        bottom = max(top + 1, min(bounds.bottom, height))
        if right <= left or bottom <= top:
            return image, None
        # 防止将过小的窗口图像发送给 VLM（API 要求 >= 10px）
        if right - left < 20 or bottom - top < 20:
            return image, None
        return image.crop((left, top, right, bottom)), WindowBounds(left, top, right, bottom)

    def split_zones(self, image: Image.Image) -> ScreenZones:
        """按比例将图像划分为左导航栏、顶部工具栏和内容区。"""
        width, height = image.size
        left_nav_width = max(1, int(width * 0.18))
        top_bar_height = max(1, int(height * 0.12))
        return ScreenZones(
            left_nav=(0, 0, left_nav_width, height),
            top_bar=(0, 0, width, top_bar_height),
            content=(left_nav_width, top_bar_height, width, height),
        )

    def crop_zone(self, image: Image.Image, zone: tuple[int, int, int, int]) -> Image.Image:
        """裁剪图像中指定区域子图。"""
        return image.crop(zone)

    def mark_step(self, before_path: str, after_path: str, keep: bool, verdict: str, extra_paths: list[str] | None = None) -> None:
        """标记步骤完成：根据 keep 标志决定是否删除截图文件并更新索引。"""
        if keep:
            return
        all_paths = [before_path, after_path]
        if extra_paths:
            all_paths.extend(extra_paths)
        unique_paths = []
        for raw_path in all_paths:
            if raw_path and raw_path not in unique_paths:
                unique_paths.append(raw_path)
        for raw_path in unique_paths:
            path = Path(raw_path)
            if path.exists():
                path.unlink()
        self._entries = [e for e in self._entries if e["path"] not in set(unique_paths)]
        self._write_index(extra={"last_verdict": verdict})

    def cleanup_sessions(self, keep_latest: int, max_age_hours: int) -> None:
        """清理过期和超出数量限制的截图会话目录。"""
        if not self.output_dir.exists():
            return

        sessions = [p for p in self.output_dir.iterdir() if p.is_dir()]
        sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        keep_set = {p.name for p in sessions[:keep_latest]}
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        for session_dir in sessions:
            if session_dir.name == self.session_id:
                continue
            if session_dir.name in keep_set:
                continue
            modified = datetime.fromtimestamp(session_dir.stat().st_mtime)
            if modified < cutoff:
                shutil.rmtree(session_dir, ignore_errors=True)

    @property
    def screen_size(self) -> tuple[int, int]:
        """返回主显示器分辨率 (width, height)。"""
        with mss.mss() as sct:
            m = sct.monitors[1]
            return m["width"], m["height"]

    def _write_index(self, extra: dict | None = None) -> None:
        """将截图条目列表写入当前会话的 index.json 文件。"""
        payload = {
            "session_id": self.session_id,
            "entries": self._entries,
        }
        if extra:
            payload.update(extra)
        self.index_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


_default_screenshot: Screenshot | None = None


def get_screenshot() -> Screenshot:
    """获取全局单例 Screenshot 实例（惰性初始化）。"""
    global _default_screenshot
    if _default_screenshot is None:
        _default_screenshot = Screenshot()
    return _default_screenshot
