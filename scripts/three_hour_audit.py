#!/usr/bin/env python3
"""Repeat the local verification loop for a real elapsed duration."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_once() -> int:
    commands = [
        ["python3", "-m", "unittest", "tests/test_agentic_autobiography.py"],
        ["python3", "scripts/agentic_autobiography.py", "index", "--docs", "docs", "samples"],
        ["python3", "scripts/agentic_autobiography.py", "journal", "--hours", "24", "--docs", "docs", "samples"],
        ["python3", "scripts/agentic_autobiography.py", "render-dashboard"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode != 0:
            return result.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated verification for a real duration.")
    parser.add_argument("--duration-seconds", type=int, default=10800)
    parser.add_argument("--interval-seconds", type=int, default=600)
    args = parser.parse_args()

    deadline = time.monotonic() + args.duration_seconds
    iteration = 0
    while True:
        iteration += 1
        print(f"audit iteration {iteration}")
        code = run_once()
        if code != 0:
            return code
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(args.interval_seconds, remaining))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
