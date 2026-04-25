#!/usr/bin/env python3
"""CUA-Lark CLI: run single steps, test suites, or interactive sessions."""

import argparse
import json
import sys
from pathlib import Path

from cua_lark.orchestrator import Orchestrator


def fmt_result(r):
    status = "PASS" if r.verdict_passed else "FAIL"
    return (
        f"[{status}] {r.instruction[:60]}\n"
        f"  Action: {type(r.action).__name__ if r.action else 'N/A'}\n"
        f"  Reason: {r.verdict_reason}\n"
        f"  Time:   {r.elapsed_ms:.0f}ms\n"
        f"  Before: {r.before_path}\n"
        f"  After:  {r.after_path}"
    )


def run_single(instruction: str):
    orch = Orchestrator()
    result = orch.run_step(instruction)
    print(fmt_result(result))


def run_test_suite(suite_path: str):
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

        print(f"\n--- Test {i + 1}/{len(test_cases)}: {instruction[:80]} ---")
        result = orch.run_step(instruction)
        print(fmt_result(result))

        if result.verdict_passed:
            passed += 1
        else:
            failed += 1

    print(f"\n=== Suite Complete: {passed} passed, {failed} failed ===")


def run_interactive():
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

        result = orch.run_step(instruction)
        print(fmt_result(result))
        print()


def main():
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

    args = parser.parse_args()

    if args.test_suite:
        run_test_suite(args.test_suite)
    elif args.interactive:
        run_interactive()
    elif args.instruction:
        run_single(args.instruction)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
