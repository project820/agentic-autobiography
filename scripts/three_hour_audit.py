#!/usr/bin/env python3
"""Repeat the local verification loop for a real elapsed duration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "three_hour_audit_state.json"
AUDIT_OUTPUT_DIR = ROOT / "data" / "audit-runtime"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_state(payload: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_env() -> dict[str, str]:
    env = os.environ.copy()
    env["AGENTIC_AUTOBIOGRAPHY_DATA_DIR"] = str(AUDIT_OUTPUT_DIR / "data")
    env["AGENTIC_AUTOBIOGRAPHY_DASHBOARD_PATH"] = str(AUDIT_OUTPUT_DIR / "dashboard" / "index.html")
    return env


def run_once(iteration: int) -> list[dict]:
    commands = [
        ["python3", "-m", "unittest", "tests/test_agentic_autobiography.py"],
        ["python3", "scripts/agentic_autobiography.py", "index", "--docs", "docs", "samples"],
        [
            "python3",
            "scripts/agentic_autobiography.py",
            "journal",
            "--hours",
            "24",
            "--docs",
            "docs",
            "samples",
            "--activity-roots",
            "docs",
            "samples",
        ],
        ["python3", "scripts/agentic_autobiography.py", "render-dashboard"],
    ]
    results = []
    for command in commands:
        started_at = utc_now()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=audit_env())
        output = (result.stdout + result.stderr).strip()
        entry = {
            "iteration": iteration,
            "command": command,
            "started_at": started_at,
            "finished_at": utc_now(),
            "returncode": result.returncode,
            "output_tail": output[-2000:],
        }
        results.append(entry)
        print(
            f"iteration={iteration} rc={result.returncode} command={' '.join(command)}",
            flush=True,
        )
        if result.returncode != 0:
            break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated verification for a real duration.")
    parser.add_argument("--duration-seconds", type=int, default=10800)
    parser.add_argument("--interval-seconds", type=int, default=600)
    args = parser.parse_args()

    started_at = utc_now()
    deadline = time.monotonic() + args.duration_seconds
    iteration = 0
    state = {
        "status": "running",
        "started_at": started_at,
        "finished_at": None,
        "duration_seconds": args.duration_seconds,
        "interval_seconds": args.interval_seconds,
        "iterations": [],
    }
    write_state(state)
    while True:
        iteration += 1
        print(f"audit iteration {iteration} started_at={utc_now()}", flush=True)
        results = run_once(iteration)
        state["iterations"].append(
            {
                "iteration": iteration,
                "started_at": results[0]["started_at"] if results else utc_now(),
                "finished_at": results[-1]["finished_at"] if results else utc_now(),
                "ok": bool(results) and all(item["returncode"] == 0 for item in results),
                "commands": results,
            }
        )
        write_state(state)
        if not state["iterations"][-1]["ok"]:
            state["status"] = "failed"
            state["finished_at"] = utc_now()
            write_state(state)
            return 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(args.interval_seconds, remaining))
    state["status"] = "passed"
    state["finished_at"] = utc_now()
    write_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
