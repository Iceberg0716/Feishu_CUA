from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from reports.generator import generate as generate_report
from runtime.config import load_yaml_config
from runtime.diagnostics import check_vlm_connectivity
from runtime.env import load_dotenv
from runtime.runner import Runner


def build_parser() -> argparse.ArgumentParser:
    # NOTE: Users often place `--config` after subcommands, e.g.
    # `python main.py run ... --config config.yaml`. Argparse only accepts
    # options after a subcommand if the subparser defines them, so we register
    # `--config` in both the root parser and subparsers. To avoid the subparser
    # default overwriting a root-provided value, we suppress the subparser
    # default and let the root parser provide the actual default.
    root_common = argparse.ArgumentParser(add_help=False)
    root_common.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML (default: config.yaml).",
    )

    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="Path to config YAML (default: config.yaml).",
    )

    parser = argparse.ArgumentParser(
        prog="lark-cua-test-agent",
        description="CUA test agent for Feishu/Lark desktop (MVP skeleton).",
        parents=[root_common],
    )

    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run one or more testcase YAML files.", parents=[sub_common])
    run_p.add_argument("testcases", nargs="+", help="YAML testcase paths.")
    run_p.add_argument(
        "--artifacts-dir",
        default=None,
        help="Override artifacts base dir (default: from config).",
    )

    sub.add_parser("doctor", help="Print environment hints.", parents=[sub_common])

    return parser


def cmd_doctor() -> int:
    print("Doctor:")
    print("- Config: use `--config config.yaml` (copy from config.example.yaml).")
    print("- Env: put secrets in `.env` (see `.env.example`).")
    print("- Feishu/Lark desktop must be running and logged in.")
    load_dotenv(".env", override=False)

    def _check_import(mod: str) -> None:
        try:
            __import__(mod)
            print(f"- import {mod}: OK")
        except Exception as exc:
            print(f"- import {mod}: FAIL ({exc})")

    _check_import("pyautogui")
    _check_import("pywinauto")
    _check_import("paddleocr")
    _check_import("paddle")

    for k in ["VLM_BASE_URL", "VLM_MODEL", "DASHSCOPE_API_KEY"]:
        v = os.environ.get(k)
        if not v:
            print(f"- env {k}: NOT SET")
            continue
        if k.endswith("_KEY"):
            if "PASTE_YOUR_KEY_HERE" in v or v.strip().lower().startswith("your_key"):
                print(f"- env {k}: SET (placeholder)")
            else:
                print(f"- env {k}: SET (masked)")
            continue
        print(f"- env {k}: SET ({v})")

    # Connectivity check (best effort): helps validate that the key works (not just "set").
    base_url = os.environ.get("VLM_BASE_URL")
    model = os.environ.get("VLM_MODEL")
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    ping = check_vlm_connectivity(base_url=base_url, api_key=api_key, model=model, timeout_seconds=8)
    if ping["ok"]:
        print("- vlm ping: OK")
    else:
        print(f"- vlm ping: FAIL ({ping['error']})")
    return 0


def cmd_run(testcases: Sequence[str], *, config_path: str, artifacts_dir: str | None) -> int:
    missing = [p for p in testcases if not Path(p).exists()]
    if missing:
        print("Testcase not found:")
        for p in missing:
            print(f"- {p}")
        return 2

    config = load_yaml_config(config_path)
    base = artifacts_dir or str(config.get("runtime", {}).get("run_dir") or "artifacts/runs")
    try:
        runner = Runner(config=config, artifacts_base=Path(base))
        run = runner.run_files(list(testcases))
        run_dir = (Path(base) / run.run_id).resolve()
        out = generate_report(run, run_dir)
    except Exception as exc:
        print(f"Run failed: {exc}")
        return 5

    print(f"Run dir: {run_dir}")
    print(f"Cases: {len(run.cases)}, Passed: {sum(1 for c in run.cases if c.success)}, Failed: {sum(1 for c in run.cases if not c.success)}")
    print(f"Report (md): {out.get('report_md')}")
    print(f"Report (html): {out.get('report_html')}")

    if all(c.success for c in run.cases):
        return 0

    failed = next((c for c in run.cases if not c.success), None)
    if failed is not None:
        print(f"First failure: {failed.case_id}")
        if failed.error:
            print(f"- Error: {failed.error}")
        if failed.steps:
            last = failed.steps[-1]
            if not last.success and last.error:
                print(f"- Step: {last.step_id} {last.name}: {last.error}")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "doctor":
        return cmd_doctor()

    if args.command == "run":
        return cmd_run(args.testcases, config_path=args.config, artifacts_dir=args.artifacts_dir)

    parser.error(f"Unknown command: {args.command}")
    return 2
