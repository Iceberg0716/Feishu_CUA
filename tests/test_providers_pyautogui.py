from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

from providers.pyautogui_provider import ProviderDependencyError, PyAutoGUIProvider


class _DummyImage:
    def __init__(self) -> None:
        self.saved_to: str | None = None

    def save(self, path: str) -> None:
        self.saved_to = path
        Path(path).write_bytes(b"fake-image")


class _DummyPyAutoGUI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self._image = _DummyImage()

    def click(self, x: int, y: int, *, clicks: int, interval: float, button: str) -> None:
        self.calls.append(("click", (x, y), {"clicks": clicks, "interval": interval, "button": button}))

    def write(self, text: str, *, interval: float) -> None:
        self.calls.append(("write", (text,), {"interval": interval}))

    def hotkey(self, *keys: str) -> None:
        self.calls.append(("hotkey", keys, {}))

    def scroll(self, clicks: int) -> None:
        self.calls.append(("scroll", (clicks,), {}))

    def screenshot(self) -> _DummyImage:
        self.calls.append(("screenshot", (), {}))
        return self._image


class TestPyAutoGUIProvider(unittest.TestCase):
    def test_requires_dependency_if_not_provided(self) -> None:
        with self.assertRaises(ProviderDependencyError):
            PyAutoGUIProvider(pyautogui_module=None, auto_import=False)

    def test_click_delegates_to_pyautogui(self) -> None:
        dummy = _DummyPyAutoGUI()
        provider = PyAutoGUIProvider(pyautogui_module=dummy, auto_import=False)
        provider.click(10, 20, clicks=2, interval=0.1, button="left")
        self.assertEqual(dummy.calls[0][0], "click")
        self.assertEqual(dummy.calls[0][1], (10, 20))
        self.assertEqual(dummy.calls[0][2]["clicks"], 2)

    def test_type_text_delegates_to_pyautogui(self) -> None:
        class _DummyPyperclip:
            last: str | None = None

            @classmethod
            def copy(cls, text: str) -> None:
                cls.last = text

        sys.modules.setdefault("pyperclip", _DummyPyperclip)

        dummy = _DummyPyAutoGUI()
        provider = PyAutoGUIProvider(pyautogui_module=dummy, auto_import=False)
        provider.type_text("hello", interval=0.02)
        self.assertEqual(_DummyPyperclip.last, "hello")
        self.assertEqual(dummy.calls[0][0], "hotkey")
        self.assertEqual(dummy.calls[0][1], ("ctrl", "v"))

    def test_hotkey_delegates_to_pyautogui(self) -> None:
        dummy = _DummyPyAutoGUI()
        provider = PyAutoGUIProvider(pyautogui_module=dummy, auto_import=False)
        provider.hotkey("ctrl", "k")
        self.assertEqual(dummy.calls[0][0], "hotkey")
        self.assertEqual(dummy.calls[0][1], ("ctrl", "k"))

    def test_scroll_delegates_to_pyautogui(self) -> None:
        dummy = _DummyPyAutoGUI()
        provider = PyAutoGUIProvider(pyautogui_module=dummy, auto_import=False)
        provider.scroll(-300)
        self.assertEqual(dummy.calls[0][0], "scroll")
        self.assertEqual(dummy.calls[0][1], (-300,))

    def test_screenshot_saves_to_path(self) -> None:
        dummy = _DummyPyAutoGUI()
        provider = PyAutoGUIProvider(pyautogui_module=dummy, auto_import=False)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "shots" / "a.png"
            saved = provider.screenshot(out)
            self.assertTrue(Path(saved).exists())
            self.assertEqual(Path(saved).read_bytes(), b"fake-image")


if __name__ == "__main__":
    unittest.main()
