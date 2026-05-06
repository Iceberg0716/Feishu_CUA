from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from providers.errors import ProviderActionError, ProviderDependencyError


class PyAutoGUIProvider:
    def __init__(self, pyautogui_module: Any | None = None, *, auto_import: bool = True) -> None:
        if pyautogui_module is None:
            if not auto_import:
                raise ProviderDependencyError("pyautogui is required but not provided")
            try:
                import pyautogui as _pyautogui  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise ProviderDependencyError(f"failed to import pyautogui: {exc}") from exc
            pyautogui_module = _pyautogui

        self._pyautogui = pyautogui_module
        try:
            self._pyautogui.FAILSAFE = True
        except Exception:
            pass

    def screenshot(self, path: str | Path) -> str:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            img = self._pyautogui.screenshot()
            img.save(str(p))
            return str(p)
        except Exception as exc:
            raise ProviderActionError("screenshot", str(exc)) from exc

    def screenshot_region(self, path: str | Path, *, left: int, top: int, width: int, height: int) -> str:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            region = (int(left), int(top), int(width), int(height))
            img = self._pyautogui.screenshot(region=region)
            img.save(str(p))
            return str(p)
        except Exception as exc:
            raise ProviderActionError("screenshot_region", str(exc)) from exc

    def click(
        self,
        x: int,
        y: int,
        *,
        clicks: int = 1,
        interval: float = 0.0,
        button: str = "left",
    ) -> None:
        try:
            self._pyautogui.click(x, y, clicks=clicks, interval=interval, button=button)
        except Exception as exc:
            raise ProviderActionError("click", str(exc)) from exc

    def type_text(self, text: str, *, interval: float = 0.0, replace: bool = False) -> None:
        try:
            try:
                import pyperclip  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise ProviderDependencyError(f"pyperclip is required for non-ascii input: {exc}") from exc

            # Prefer clipboard paste for ALL text (ASCII included) to avoid IME/layout glitches and partial typing.
            # This is more stable for desktop app automation at the cost of touching the user's clipboard.
            if replace:
                self._pyautogui.hotkey("ctrl", "a")
                time.sleep(0.03)
                self._pyautogui.press("backspace")
                time.sleep(0.03)

            pyperclip.copy(text)
            time.sleep(0.05)
            self._pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)
        except Exception as exc:
            raise ProviderActionError("type_text", str(exc)) from exc

    def hotkey(self, *keys: str) -> None:
        try:
            self._pyautogui.hotkey(*keys)
        except Exception as exc:
            raise ProviderActionError("hotkey", str(exc)) from exc

    def press(self, key: str, *, presses: int = 1, interval: float = 0.0) -> None:
        try:
            self._pyautogui.press(str(key), presses=int(presses), interval=float(interval))
        except Exception as exc:
            raise ProviderActionError("press", str(exc)) from exc

    def move_to(self, x: int, y: int, *, duration: float = 0.05) -> None:
        try:
            self._pyautogui.moveTo(int(x), int(y), duration=float(duration))
        except Exception as exc:
            raise ProviderActionError("move_to", str(exc)) from exc

    def scroll(self, clicks: int, *, x: int | None = None, y: int | None = None) -> None:
        try:
            if x is not None and y is not None:
                self.move_to(int(x), int(y), duration=0.05)
            self._pyautogui.scroll(clicks)
        except Exception as exc:
            raise ProviderActionError("scroll", str(exc)) from exc
