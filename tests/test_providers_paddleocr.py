from __future__ import annotations

import unittest

from providers.paddleocr_provider import PaddleOCRProvider, ProviderActionError, ProviderDependencyError


class _DummyEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def ocr(self, img_path: str, cls: bool = True):  # noqa: ANN001
        self.calls.append((img_path, cls))
        return [
            [
                ([(0, 0), (100, 0), (100, 20), (0, 20)], ("Hello", 0.98)),
                ([(0, 30), (100, 30), (100, 50), (0, 50)], ("World", 0.95)),
            ]
        ]


class _BoomEngine:
    def ocr(self, img_path: str, cls: bool = True):  # noqa: ANN001
        raise RuntimeError("boom")


class TestPaddleOCRProvider(unittest.TestCase):
    def test_requires_dependency_if_not_provided(self) -> None:
        with self.assertRaises(ProviderDependencyError):
            PaddleOCRProvider(ocr_engine=None, auto_import=False)

    def test_extract_text_normalizes_result(self) -> None:
        dummy = _DummyEngine()
        provider = PaddleOCRProvider(ocr_engine=dummy, auto_import=False)
        items = provider.extract_text("a.png")
        self.assertEqual(dummy.calls[0][0], "a.png")
        self.assertTrue(dummy.calls[0][1])
        self.assertEqual([i["text"] for i in items], ["Hello", "World"])
        self.assertEqual(items[0]["bbox"], [0, 0, 100, 20])
        self.assertAlmostEqual(items[0]["confidence"], 0.98, places=3)

    def test_wraps_engine_errors(self) -> None:
        provider = PaddleOCRProvider(ocr_engine=_BoomEngine(), auto_import=False)
        with self.assertRaises(ProviderActionError) as ctx:
            provider.extract_text("a.png")
        self.assertIn("ocr_extract failed:", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

