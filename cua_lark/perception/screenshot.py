"""Cross-platform screen capture using mss with session-aware retention."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import mss
from PIL import Image


class Screenshot:
    def __init__(self, output_dir: str = "logs/screenshots", prefix: str = "step_"):
        self.output_dir = Path(output_dir)
        self.prefix = prefix
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / self.session_id
        self.counter = 0
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.session_dir / "index.json"
        self._entries: list[dict] = []

    def capture(self, role: str, instruction: str = "", monitor_index: int = 1) -> tuple[Image.Image, str]:
        """Capture primary monitor screenshot. Returns (PIL.Image, filepath)."""
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

    def mark_step(self, before_path: str, after_path: str, keep: bool, verdict: str) -> None:
        """Delete only the screenshots for one step when the policy says they are disposable."""
        if keep:
            return
        for raw_path in (before_path, after_path):
            path = Path(raw_path)
            if path.exists():
                path.unlink()
        self._entries = [e for e in self._entries if e["path"] not in {before_path, after_path}]
        self._write_index(extra={"last_verdict": verdict})

    def cleanup_sessions(self, keep_latest: int, max_age_hours: int) -> None:
        """Remove expired session directories without touching recent sessions."""
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
        with mss.mss() as sct:
            m = sct.monitors[1]
            return m["width"], m["height"]

    def _write_index(self, extra: dict | None = None) -> None:
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
    global _default_screenshot
    if _default_screenshot is None:
        _default_screenshot = Screenshot()
    return _default_screenshot
