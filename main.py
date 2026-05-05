#!/usr/bin/env python3
"""CUA-Lark CLI: run single steps, test suites, or interactive sessions."""

import argparse
import json
import sys
import time
from pathlib import Path

from cua_lark.orchestrator import Orchestrator


def fmt_result(r):
    """将 StepResult 格式化为可读的终端输出。"""
    status = "PASS" if r.verdict_passed else "FAIL"
    return (
        f"[{status}] {r.instruction[:60]}\n"
        f"  Action: {type(r.action).__name__ if r.action else 'N/A'}\n"
        f"  Reason: {r.verdict_reason}\n"
        f"  Time:   {r.elapsed_ms:.0f}ms\n"
        f"  Before: {r.before_path}\n"
        f"  After:  {r.after_path}"
    )


def _normalize_delay(delay_seconds: float | int | None) -> float:
    return max(0.0, float(delay_seconds or 0.0))


def _wait_before_execution(delay_seconds: float) -> None:
    delay_seconds = _normalize_delay(delay_seconds)
    if delay_seconds <= 0:
        return
    print(f"Waiting {delay_seconds:g}s before executing...")
    time.sleep(delay_seconds)


def run_single(instruction: str, delay_seconds: float = 0.0):
    """执行单条指令并打印结果。"""
    orch = Orchestrator()
    _wait_before_execution(delay_seconds)
    result = orch.run_step(instruction)
    print(fmt_result(result))


def run_test_suite(suite_path: str, delay_seconds: float = 0.0):
    """从 JSON 文件加载测试用例列表，逐条执行并统计通过/失败数。"""
    suite_file = Path(suite_path)
    if not suite_file.exists():
        print(f"Test suite file not found: {suite_path}")
        sys.exit(1)

    with open(suite_file, encoding="utf-8") as f:
        test_cases = json.load(f)

    orch = Orchestrator()
    passed = 0
    failed = 0

    for i, tc in enumerate(test_cases):
        instruction = tc.get("instruction", "")
        expected_action = tc.get("expected_action", "")
        case_delay = _normalize_delay(tc.get("delay_seconds", delay_seconds))

        print(f"\n--- Test {i + 1}/{len(test_cases)}: {instruction[:80]} ---")
        _wait_before_execution(case_delay)
        result = orch.run_step(instruction)
        print(fmt_result(result))

        if result.verdict_passed:
            passed += 1
        else:
            failed += 1

    print(f"\n=== Suite Complete: {passed} passed, {failed} failed ===")


def run_interactive(delay_seconds: float = 0.0):
    """启动交互模式，持续接收用户输入并执行，直到输入 quit/exit/q。"""
    print("CUA-Lark Interactive Mode")
    print("Type your instruction and press Enter. Type 'quit' to exit.\n")

    orch = Orchestrator()
    while True:
        try:
            instruction = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not instruction:
            continue
        if instruction.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        _wait_before_execution(delay_seconds)
        result = orch.run_step(instruction)
        print(fmt_result(result))
        print()


def main():
    """CLI 入口，解析命令行参数并分发到对应运行模式。"""
    parser = argparse.ArgumentParser(
        description="CUA-Lark: Computer-Use Agent for Lark/Feishu"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-i", "--instruction", type=str, help="Single instruction to execute"
    )
    group.add_argument(
        "-t", "--test-suite", type=str, help="Path to JSON test suite file"
    )
    group.add_argument(
        "--interactive", action="store_true", help="Interactive mode"
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.0,
        help="Seconds to wait before executing each instruction",
    )

    args = parser.parse_args()

    if args.test_suite:
        run_test_suite(args.test_suite, delay_seconds=args.delay_seconds)
    elif args.interactive:
        run_interactive(delay_seconds=args.delay_seconds)
    elif args.instruction:
        run_single(args.instruction, delay_seconds=args.delay_seconds)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
