from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from runtime.models import RunResult


def _env() -> Environment:
    templates_dir = Path(__file__).parent / "templates"
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )


def generate(run: RunResult, run_dir: str | Path) -> dict[str, str]:
    out_dir = Path(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env = _env()
    ctx = {
        "run": run,
        "summary": {"total": len(run.cases), "passed": sum(1 for c in run.cases if c.success), "failed": sum(1 for c in run.cases if not c.success)},
    }

    md = env.get_template("report.md.j2").render(**ctx)
    html = env.get_template("report.html.j2").render(**ctx)

    md_path = out_dir / "report.md"
    html_path = out_dir / "report.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    # also write a compact summary json for convenience
    (out_dir / "summary.json").write_text(
        json.dumps(ctx["summary"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"report_md": str(md_path), "report_html": str(html_path)}


__all__ = ["generate"]

