#!/usr/bin/env python3
"""Minimal stdio MCP server for Agentic Autobiography."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agentic_autobiography as engine


JSON = dict[str, Any]


def tool_descriptions() -> list[JSON]:
    return [
        {
            "name": "memory.search",
            "description": "Search indexed local context.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
        {
            "name": "memory.timeline",
            "description": "Build a source-grounded timeline for an entity or project.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["entity"],
            },
        },
        {
            "name": "memory.actions",
            "description": "Extract unfinished work and follow-up items.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
        {
            "name": "memory.summary",
            "description": "Generate a recovered context report.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "journal.generate",
            "description": "Write a daily journal from the last N hours of local context.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "default": 24},
                    "activity_roots": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional local roots to scan for recent file activity.",
                    },
                },
            },
        },
        {
            "name": "dashboard.render",
            "description": "Render the static dashboard.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def result_content(payload: Any) -> JSON:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ]
    }


def call_tool(name: str, arguments: JSON) -> JSON:
    handlers: dict[str, Callable[[JSON], Any]] = {
        "memory.search": lambda args: engine.search(args["query"], int(args.get("limit", 5))),
        "memory.timeline": lambda args: engine.timeline(args["entity"], int(args.get("limit", 10))),
        "memory.actions": lambda args: engine.extract_actions(
            engine.search(args.get("scope") or "action todo next follow-up", 20),
            int(args.get("limit", 10)),
        ),
        "memory.summary": lambda args: engine.summarize(args["query"]),
        "journal.generate": lambda args: engine.generate_journal(
            int(args.get("hours", 24)),
            activity_roots=[engine.Path(value) for value in args.get("activity_roots", [])]
            if args.get("activity_roots") is not None
            else None,
        ),
        "dashboard.render": lambda args: {"dashboard": str(engine.render_dashboard())},
    }
    if name not in handlers:
        raise ValueError(f"Unknown tool: {name}")
    return result_content(handlers[name](arguments))


def response(request_id: Any, result: Any) -> JSON:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str) -> JSON:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: JSON) -> JSON | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentic-autobiography", "version": "0.1.0"},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return response(request_id, {"tools": tool_descriptions()})
    if method == "tools/call":
        try:
            return response(request_id, call_tool(params["name"], params.get("arguments", {})))
        except Exception as exc:
            return error_response(request_id, -32000, str(exc))
    return error_response(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            payload = handle(request)
        except Exception as exc:
            payload = error_response(None, -32700, str(exc))
        if payload is not None:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
