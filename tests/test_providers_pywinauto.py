from __future__ import annotations

import unittest

from providers.pywinauto_provider import ProviderDependencyError, PywinautoProvider


class _DummyWindow:
    def __init__(self, title: str) -> None:
        self._title = title
        self.focused = False

    def window_text(self) -> str:
        return self._title

    def set_focus(self) -> None:
        self.focused = True


class _DummyDesktop:
    def __init__(self, windows: list[_DummyWindow]) -> None:
        self._windows = windows

    def windows(self) -> list[_DummyWindow]:
        return self._windows


def _desktop_factory(_: str) -> _DummyDesktop:
    return _DummyDesktop([_DummyWindow("Other"), _DummyWindow("飞书 - 工作台"), _DummyWindow("Lark | Chat")])


class TestPywinautoProvider(unittest.TestCase):
    def test_requires_dependency_if_not_provided(self) -> None:
        with self.assertRaises(ProviderDependencyError):
            PywinautoProvider(desktop_factory=None, auto_import=False)

    def test_focus_window_finds_by_keywords_and_focuses(self) -> None:
        provider = PywinautoProvider(desktop_factory=_desktop_factory, auto_import=False)
        focused_title = provider.focus_window(["飞书", "Feishu", "Lark"])
        self.assertIn("飞书", focused_title)


if __name__ == "__main__":
    unittest.main()

