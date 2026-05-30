#!/usr/bin/env python3
"""Finalize the three-hour audit and optionally send a Telegram report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "three_hour_audit_state.json"
HERMES_ENV = Path.home() / ".hermes" / ".env"
CHANNEL_DIRECTORY = Path.home() / ".hermes" / "channel_directory.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def run(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": result.returncode,
        "output_tail": (result.stdout + result.stderr).strip()[-2000:],
    }


def maybe_advance_audit_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"status": "missing", "reason": f"{STATE_PATH} does not exist"}
    state = load_json(STATE_PATH)
    if state.get("status") == "running":
        started_at = parse_time(state["started_at"])
        elapsed = (now_utc() - started_at).total_seconds()
        if elapsed >= int(state.get("duration_seconds", 10800)):
            run(["python3", "scripts/three_hour_audit_tick.py"])
            state = load_json(STATE_PATH)
    return state


def run_final_checks() -> list[dict[str, Any]]:
    checks = [
        ["python3", "-m", "unittest", "tests/test_agentic_autobiography.py"],
        [".venv/bin/python", "/Users/m5max/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py", "."],
        ["python3", "scripts/agentic_autobiography.py", "render-dashboard"],
        ["git", "diff", "--quiet"],
    ]
    return [run(command) for command in checks]


def git_evidence() -> dict[str, str]:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/main"],
        cwd=ROOT,
        text=True,
    ).split()[0]
    return {"head": head, "origin_main": remote}


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value.strip().strip('"').strip("'")
    return env


def resolve_telegram_chat(env: dict[str, str]) -> str | None:
    chat_id = env.get("TELEGRAM_HOME_CHANNEL")
    if chat_id and chat_id.lstrip("-").isdigit():
        return chat_id
    if CHANNEL_DIRECTORY.exists():
        data = load_json(CHANNEL_DIRECTORY)
        chats = data.get("platforms", {}).get("telegram", [])
        if chats:
            return str(chats[0].get("id"))
    return chat_id


def send_telegram(message: str) -> dict[str, Any]:
    env = load_env(HERMES_ENV)
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = resolve_telegram_chat(env)
    if not token or not chat_id:
        return {"ok": False, "reason": "missing Telegram token or chat id"}
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=body, timeout=20) as response:
        payload = json.loads(response.read().decode())
    return {
        "ok": payload.get("ok"),
        "message_id": payload.get("result", {}).get("message_id"),
        "chat_id": chat_id,
    }


def build_report(state: dict[str, Any], checks: list[dict[str, Any]], git: dict[str, str]) -> dict[str, Any]:
    started_at = state.get("started_at")
    elapsed = None
    if started_at:
        elapsed = int((now_utc() - parse_time(started_at)).total_seconds())
    passed_checks = all(item["returncode"] == 0 for item in checks)
    git_pushed = bool(git.get("head")) and git.get("head") == git.get("origin_main")
    audit_passed = state.get("status") == "passed"
    complete = audit_passed and passed_checks and git_pushed
    return {
        "complete": complete,
        "audit_status": state.get("status"),
        "audit_started_at": started_at,
        "audit_finished_at": state.get("finished_at"),
        "audit_elapsed_seconds": elapsed,
        "audit_iterations": len(state.get("iterations", [])),
        "checks_passed": passed_checks,
        "git_pushed": git_pushed,
        "git": git,
        "checks": checks,
    }


def message_for(report: dict[str, Any]) -> str:
    status = "완료" if report["complete"] else "미완료"
    return (
        "Agentic Autobiography 최종 검수 보고\n\n"
        f"상태: {status}\n"
        f"Repo: https://github.com/project820/agentic-autobiography\n"
        f"Audit: {report['audit_status']} / 반복 {report['audit_iterations']}회 / "
        f"경과 {report['audit_elapsed_seconds']}초\n"
        f"Checks passed: {report['checks_passed']}\n"
        f"GitHub pushed: {report['git_pushed']}\n"
        f"HEAD: {report['git']['head'][:7]}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize audit state and optionally send Telegram.")
    parser.add_argument("--send-telegram", action="store_true")
    args = parser.parse_args()

    state = maybe_advance_audit_state()
    checks = run_final_checks()
    git = git_evidence()
    report = build_report(state, checks, git)
    if args.send_telegram:
        report["telegram"] = send_telegram(message_for(report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
