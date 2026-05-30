#!/usr/bin/env python3
"""Run one durable audit tick and persist progress for launchd/automation checks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "three_hour_audit_state.json"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def write_state(payload: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def initial_state(duration_seconds: int, interval_seconds: int) -> dict:
    started_at = utc_now()
    return {
        "status": "running",
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "duration_seconds": duration_seconds,
        "interval_seconds": interval_seconds,
        "iterations": [],
    }


def load_state(duration_seconds: int, interval_seconds: int, reset: bool) -> dict:
    if reset or not STATE_PATH.exists():
        state = initial_state(duration_seconds, interval_seconds)
        write_state(state)
        return state
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if state.get("status") not in {"running", "passed"}:
        return state
    state.setdefault("duration_seconds", duration_seconds)
    state.setdefault("interval_seconds", interval_seconds)
    state.setdefault("iterations", [])
    return state


def run_command(command: list[str], iteration: int) -> dict:
    started_at = utc_now()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    return {
        "iteration": iteration,
        "command": command,
        "started_at": started_at.isoformat(),
        "finished_at": utc_now().isoformat(),
        "returncode": result.returncode,
        "output_tail": output[-2000:],
    }


def run_tick(state: dict) -> dict:
    if state.get("status") != "running":
        return state
    if state.get("iterations"):
        last_finished = parse_time(state["iterations"][-1]["finished_at"])
        elapsed_since_last = (utc_now() - last_finished).total_seconds()
        total_elapsed = (utc_now() - parse_time(state["started_at"])).total_seconds()
        interval_seconds = int(state.get("interval_seconds", 600))
        duration_seconds = int(state.get("duration_seconds", 10800))
        if elapsed_since_last < interval_seconds and total_elapsed < duration_seconds:
            state["last_skip"] = {
                "at": utc_now().isoformat(),
                "reason": "interval_not_elapsed",
                "seconds_since_last": int(elapsed_since_last),
                "interval_seconds": interval_seconds,
            }
            return state
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
    iteration = len(state["iterations"]) + 1
    results = []
    for command in commands:
        entry = run_command(command, iteration)
        results.append(entry)
        if entry["returncode"] != 0:
            break
    ok = bool(results) and all(item["returncode"] == 0 for item in results)
    state["iterations"].append(
        {
            "iteration": iteration,
            "started_at": results[0]["started_at"] if results else utc_now().isoformat(),
            "finished_at": results[-1]["finished_at"] if results else utc_now().isoformat(),
            "ok": ok,
            "commands": results,
        }
    )
    if not ok:
        state["status"] = "failed"
        state["finished_at"] = utc_now().isoformat()
        return state
    started_at = parse_time(state["started_at"])
    elapsed = (utc_now() - started_at).total_seconds()
    if elapsed >= int(state["duration_seconds"]):
        state["status"] = "passed"
        state["finished_at"] = utc_now().isoformat()
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one three-hour audit tick.")
    parser.add_argument("--duration-seconds", type=int, default=10800)
    parser.add_argument("--interval-seconds", type=int, default=600)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    state = load_state(args.duration_seconds, args.interval_seconds, args.reset)
    state = run_tick(state)
    write_state(state)
    print(
        json.dumps(
            {
                "status": state["status"],
                "started_at": state["started_at"],
                "finished_at": state.get("finished_at"),
                "iterations": len(state.get("iterations", [])),
                "last_ok": state.get("iterations", [{}])[-1].get("ok") if state.get("iterations") else None,
            },
            ensure_ascii=False,
        )
    )
    return 1 if state["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
