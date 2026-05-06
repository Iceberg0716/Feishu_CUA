from __future__ import annotations

from collections.abc import Callable
from typing import Any

from providers.errors import ProviderActionError, ProviderDependencyError


class PywinautoProvider:
    def __init__(
        self,
        desktop_factory: Callable[[str], Any] | None = None,
        *,
        backend: str = "uia",
        auto_import: bool = True,
    ) -> None:
        if desktop_factory is None:
            if not auto_import:
                raise ProviderDependencyError("pywinauto is required but not provided")
            try:
                from pywinauto import Desktop  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise ProviderDependencyError(f"failed to import pywinauto: {exc}") from exc

            desktop_factory = lambda b: Desktop(backend=b)

        self._desktop_factory = desktop_factory
        self._backend = backend

    def focus_window(self, title_keywords: list[str]) -> str:
        try:
            desktop = self._desktop_factory(self._backend)
            for win in desktop.windows():
                title = ""
                try:
                    title = str(win.window_text())
                except Exception:
                    continue
                if any(k and (k in title) for k in title_keywords):
                    win.set_focus()
                    return title
            raise ProviderActionError("focus_window", "no matching window found")
        except ProviderActionError:
            raise
        except Exception as exc:
            raise ProviderActionError("focus_window", str(exc)) from exc

    def focus_window_and_get_rect(self, title_keywords: list[str]) -> dict[str, object]:
        """
        Focus a window matching `title_keywords` and return its rect.
        Rect keys: left/top/right/bottom (int).
        """
        try:
            desktop = self._desktop_factory(self._backend)
            for win in desktop.windows():
                title = ""
                try:
                    title = str(win.window_text())
                except Exception:
                    continue
                if not any(k and (k in title) for k in title_keywords):
                    continue
                win.set_focus()
                rect = win.rectangle()
                out = {
                    "title": title,
                    "rect": {
                        "left": int(getattr(rect, "left", 0)),
                        "top": int(getattr(rect, "top", 0)),
                        "right": int(getattr(rect, "right", 0)),
                        "bottom": int(getattr(rect, "bottom", 0)),
                    },
                }
                return out
            raise ProviderActionError("focus_window", "no matching window found")
        except ProviderActionError:
            raise
        except Exception as exc:
            raise ProviderActionError("focus_window", str(exc)) from exc
