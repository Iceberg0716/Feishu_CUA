from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from reports.generator import generate
from runtime.models import CaseResult, RunResult, StepLog


class TestReportGenerator(unittest.TestCase):
    def test_generate_writes_md_and_html(self) -> None:
        step = StepLog(
            step_id="s1",
            step_type="skill",
            name="im.send_message",
            params={},
            success=True,
            started_at=datetime(2026, 5, 3, 12, 0, 0),
            ended_at=datetime(2026, 5, 3, 12, 0, 1),
            evidence=["a.png"],
            result={"ok": True},
        )
        case = CaseResult(
            case_id="c1",
            goal="g",
            success=True,
            started_at=datetime(2026, 5, 3, 12, 0, 0),
            ended_at=datetime(2026, 5, 3, 12, 0, 1),
            steps=[step],
            evidence=["a.png"],
            meta={},
        )
        run = RunResult(run_id="r1", started_at=datetime(2026, 5, 3, 12, 0, 0), ended_at=datetime(2026, 5, 3, 12, 0, 2), cases=[case])
        with tempfile.TemporaryDirectory() as td:
            out = generate(run, Path(td))
            self.assertTrue(Path(out["report_md"]).exists())
            self.assertTrue(Path(out["report_html"]).exists())


if __name__ == "__main__":
    unittest.main()

