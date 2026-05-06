from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.env import load_dotenv


class TestLoadDotenv(unittest.TestCase):
    def test_loads_simple_kv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".env"
            p.write_text("A=1\nB=hello\n# C=skip\n", encoding="utf-8")
            old = dict(os.environ)
            try:
                loaded = load_dotenv(p)
                self.assertEqual(loaded["A"], "1")
                self.assertEqual(os.environ["B"], "hello")
            finally:
                os.environ.clear()
                os.environ.update(old)

    def test_does_not_override_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".env"
            p.write_text("A=fromfile\n", encoding="utf-8")
            old = dict(os.environ)
            try:
                os.environ["A"] = "fromenv"
                load_dotenv(p, override=False)
                self.assertEqual(os.environ["A"], "fromenv")
                load_dotenv(p, override=True)
                self.assertEqual(os.environ["A"], "fromfile")
            finally:
                os.environ.clear()
                os.environ.update(old)

    def test_strips_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".env"
            p.write_text("A=\"x y\"\nB='z'\n", encoding="utf-8")
            old = dict(os.environ)
            try:
                load_dotenv(p, override=True)
                self.assertEqual(os.environ["A"], "x y")
                self.assertEqual(os.environ["B"], "z")
            finally:
                os.environ.clear()
                os.environ.update(old)


if __name__ == "__main__":
    unittest.main()

