from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from reports.generator import generate as generate_report
from runtime.config import load_yaml_config
from runtime.context import RunContext
from runtime.diagnostics import check_vlm_connectivity
from runtime.env import load_dotenv
from runtime.runner import Runner
from runtime.recorded_skill_loader import RecordedSkillLoader
from runtime.recorded_skill_registry import RecordedSkillRegistry
from runtime.recorded_planner import RecordedPlanner
from runtime.template_renderer import TemplateRenderer, TemplateRenderError
from runtime.natural_language_runner import NaturalLanguageRunner
from skills.recorded import RecordedSkillExecutor
from tools.defaults import build_default_tool_registry


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
    parser.add_argument(
        "-i",
        "--instruction",
        default=None,
        help='Natural language instruction to plan+execute via LLM (example: -i "在测试群里发送 HelloWorld").',
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

    recorded_p = sub.add_parser("recorded", help="Recorded Skill sidecar commands.", parents=[sub_common])
    recorded_sub = recorded_p.add_subparsers(dest="recorded_command")

    recorded_sub.add_parser("list", help="List recorded skills.", parents=[sub_common])

    show_p = recorded_sub.add_parser("show", help="Show a recorded skill by id or yaml path.", parents=[sub_common])
    show_p.add_argument("skill", help="Recorded skill id (e.g. recorded.im.open_chat_by_search.v1) or YAML path.")

    run_p = recorded_sub.add_parser("run", help="Run a recorded skill (requires --yes to execute tools).", parents=[sub_common])
    run_p.add_argument("skill", help="Recorded skill id or YAML path.")
    run_p.add_argument("--param", action="append", default=[], help="Param in key=value format (repeatable).")
    run_p.add_argument("--yes", action="store_true", help="Actually execute tools (side effects). Default is dry-run.")
    run_p.add_argument("--start-step", default=None, help="Start from this step id (non-composed skill).")
    run_p.add_argument("--end-step", default=None, help="End at this step id (non-composed skill).")

    plan_p = recorded_sub.add_parser("plan", help="Plan a task using recorded skills (no execution).", parents=[sub_common])
    # Backward compatible: accept both positional (old) and flags (new).
    plan_p.add_argument("product", nargs="?", help="Product, e.g. im (or use --product).")
    plan_p.add_argument("intent", nargs="?", help="Intent, e.g. send_message (or use --intent).")
    plan_p.add_argument("--product", dest="product_opt", default=None, help="Product, e.g. im.")
    plan_p.add_argument("--intent", dest="intent_opt", default=None, help="Intent, e.g. send_emoji.")
    plan_p.add_argument("--param", action="append", default=[], help="Param in key=value format (repeatable).")
    plan_p.add_argument("--state", action="append", default=[], help="Current state item (repeatable).")

    return parser


def _vision_ocr_enabled(config: dict) -> bool:
    vision = config.get("vision") if isinstance(config.get("vision"), dict) else {}
    if isinstance(vision, dict) and "ocr_enabled" in vision:
        return bool(vision.get("ocr_enabled"))
    ocr = config.get("ocr") if isinstance(config.get("ocr"), dict) else {}
    return bool(ocr.get("enabled", True))


def cmd_doctor(*, config_path: str) -> int:
    print("Doctor:")
    print("- Config: use `--config config.yaml` (copy from config.example.yaml).")
    print("- Env: put secrets in `.env` (see `.env.example`).")
    print("- Feishu/Lark desktop must be running and logged in.")
    load_dotenv(".env", override=False)
    try:
        config = load_yaml_config(config_path)
    except Exception as exc:
        print(f"- config load: WARN ({exc})")
        config = {}

    def _check_import(mod: str) -> None:
        try:
            __import__(mod)
            print(f"- import {mod}: OK")
        except Exception as exc:
            print(f"- import {mod}: WARN ({exc})")

    _check_import("pyautogui")
    _check_import("pywinauto")
    if _vision_ocr_enabled(config):
        _check_import("paddleocr")
        _check_import("paddle")
    else:
        print("- ocr: DISABLED (skip paddleocr/paddle import checks)")

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


def _parse_kv_params(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"--param must be key=value, got: {raw}")
        k, v = raw.split("=", 1)
        k = k.strip()
        if not k:
            raise ValueError(f"--param key is empty: {raw}")
        out[k] = v
    return out


def _build_recorded_registry() -> RecordedSkillRegistry:
    loader = RecordedSkillLoader()
    skills = loader.load_dir("recorded_skills")
    return RecordedSkillRegistry(skills)


def _resolve_recorded_skill(skill_id_or_path: str, *, loader: RecordedSkillLoader, registry: RecordedSkillRegistry):
    p = Path(skill_id_or_path)
    if p.exists() and p.is_file():
        return loader.load_path(p)
    if skill_id_or_path.endswith(".yaml") or skill_id_or_path.endswith(".yml"):
        return loader.load_path(skill_id_or_path)
    return registry.get(skill_id_or_path)


def _recorded_dry_run_print(skill, *, params: dict[str, str], registry: RecordedSkillRegistry) -> None:
    renderer = TemplateRenderer()
    print(f"Recorded skill: {skill.id} ({skill.name})")
    print(f"- product={skill.metadata.product}, intent={skill.metadata.intent}, status={skill.metadata.status}, side_effect={skill.metadata.side_effect}")
    if skill.is_composed():
        print("- composed_of:")
        for ref in skill.composed_of or []:
            try:
                child = registry.get(ref.skill)
            except Exception:
                child = None
            rendered = renderer.render(ref.params, params=params, vars={})
            print(f"  - {ref.skill}" + (f" ({child.name})" if child else ""))
            print(f"    params: {rendered}")
        return

    vars: dict[str, object] = {}
    for step in skill.steps:
        try:
            rendered_params = renderer.render(step.params, params=params, vars=vars)
        except TemplateRenderError as exc:
            rendered_params = {"_render_error": str(exc)}
        print(f"- step {step.id}: {step.tool}")
        print(f"  params: {rendered_params}")
        if step.save_as:
            print(f"  save_as: {step.save_as}")
        if step.wait_after is not None:
            print(f"  wait_after: {step.wait_after}")


def cmd_recorded_list(*, config_path: str) -> int:  # config_path kept for consistent CLI shape
    reg = _build_recorded_registry()
    for s in reg.list():
        print(f"{s.id}\t[{s.metadata.product}/{s.metadata.intent}]\t{s.metadata.status}\t{s.name}")
    return 0


def cmd_recorded_show(skill_id_or_path: str, *, config_path: str) -> int:  # config_path kept for consistent CLI shape
    loader = RecordedSkillLoader()
    reg = _build_recorded_registry()
    skill = _resolve_recorded_skill(skill_id_or_path, loader=loader, registry=reg)
    import json

    print(json.dumps(skill.model_dump(), ensure_ascii=False, indent=2))
    return 0


def cmd_recorded_plan(
    product: str | None,
    intent: str | None,
    *,
    raw_params: list[str],
    raw_state: list[str],
    config_path: str,  # noqa: ARG001
) -> int:
    if not product or not intent:
        print("recorded plan requires product and intent (use positional args or --product/--intent).")
        return 2

    reg = _build_recorded_registry()
    params = _parse_kv_params(raw_params)
    planner = RecordedPlanner(registry=reg)
    plan = planner.plan(product=product, intent=intent, params=params, current_state=raw_state)

    import json

    print(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2))
    return 0 if plan.complete else 1


def cmd_recorded_run(
    skill_id_or_path: str,
    *,
    raw_params: list[str],
    yes: bool,
    start_step: str | None,
    end_step: str | None,
    config_path: str,
) -> int:
    loader = RecordedSkillLoader()
    reg = _build_recorded_registry()
    skill = _resolve_recorded_skill(skill_id_or_path, loader=loader, registry=reg)
    params = _parse_kv_params(raw_params)

    if not yes:
        print("Dry-run mode: tools will NOT be executed. Re-run with `--yes` to execute.")
        _recorded_dry_run_print(skill, params=params, registry=reg)
        return 0

    config = load_yaml_config(config_path)
    tool_registry = build_default_tool_registry(config)
    executor = RecordedSkillExecutor(tool_registry=tool_registry, skill_registry=reg, loader=loader)

    from datetime import datetime

    run_id = "recorded_" + datetime.now().strftime("%Y-%m-%d_%H%M%S")
    artifacts = Path(str(config.get("runtime", {}).get("run_dir") or "artifacts/runs")) / run_id
    artifacts.mkdir(parents=True, exist_ok=True)
    from runtime.providers import build_providers

    providers = build_providers(config)
    ctx = RunContext(run_id=run_id, artifacts_dir=artifacts, tool_registry=tool_registry, metadata={"config": config, "providers": providers})

    res = executor.execute(skill, params=params, context=ctx, start_step=start_step, end_step=end_step)
    if res.success:
        print(f"Recorded run OK: {skill.id}")
        return 0
    print(f"Recorded run FAIL: {skill.id}")
    if res.failed_step:
        print(f"- failed_step: {res.failed_step}")
    if res.error:
        print(f"- error: {res.error}")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if getattr(args, "instruction", None):
        if args.command is not None:
            parser.error("`-i/--instruction` cannot be combined with subcommands (run/doctor/recorded).")
            return 2
        runner = NaturalLanguageRunner(config_path=args.config)
        res = runner.run(str(args.instruction))
        if res.success:
            return 0
        print(f"Result: {str(res.status).upper()}")
        print(f"Error: {res.error or '(no error message)'}")
        if res.resolved_plan is not None and str(res.status).lower() in {"rejected", "missing_params", "missing_capability", "clarification_required"}:
            import json

            print("Debug:")
            print(json.dumps(res.resolved_plan, ensure_ascii=False, indent=2))
        return 1

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "doctor":
        return cmd_doctor(config_path=args.config)

    if args.command == "run":
        return cmd_run(args.testcases, config_path=args.config, artifacts_dir=args.artifacts_dir)

    if args.command == "recorded":
        if args.recorded_command is None:
            # Show `recorded` help.
            try:
                build_parser().parse_args([args.command, "--help"])
            except SystemExit:
                pass
            return 0
        if args.recorded_command == "list":
            return cmd_recorded_list(config_path=args.config)
        if args.recorded_command == "show":
            return cmd_recorded_show(args.skill, config_path=args.config)
        if args.recorded_command == "plan":
            product = getattr(args, "product_opt", None) or getattr(args, "product", None)
            intent = getattr(args, "intent_opt", None) or getattr(args, "intent", None)
            return cmd_recorded_plan(product, intent, raw_params=args.param, raw_state=args.state, config_path=args.config)
        if args.recorded_command == "run":
            return cmd_recorded_run(
                args.skill,
                raw_params=args.param,
                yes=bool(args.yes),
                start_step=args.start_step,
                end_step=args.end_step,
                config_path=args.config,
            )
        parser.error(f"Unknown recorded command: {args.recorded_command}")
        return 2

    parser.error(f"Unknown command: {args.command}")
    return 2
