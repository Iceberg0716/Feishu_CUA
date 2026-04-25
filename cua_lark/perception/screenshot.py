"""Cross-platform screen capture using mss."""

import os
import time
from datetime import datetime
from pathlib import Path

import mss
from PIL import Image


class Screenshot:
    def __init__(self, output_dir: str = "logs/screenshots", prefix: str = "step_"):
        self.output_dir = output_dir
        self.prefix = prefix
        self.counter = 0
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def capture(self, monitor_index: int = 1) -> tuple[Image.Image, str]:
        """Capture primary monitor screenshot. Returns (PIL.Image, filepath)."""
        with mss.mss() as sct:
            monitor = sct.monitors[monitor_index]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        self.counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{self.prefix}{self.counter:04d}_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath, "PNG")

        return img, filepath

    @property
    def screen_size(self) -> tuple[int, int]:
        with mss.mss() as sct:
            m = sct.monitors[1]
            return m["width"], m["height"]


_default_screenshot: Screenshot | None = None


def get_screenshot() -> Screenshot:
    global _default_screenshot
    if _default_screenshot is None:
        _default_screenshot = Screenshot()
    return _default_screenshot
