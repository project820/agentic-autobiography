# Agentic Autobiography

한국어 README: [README.ko.md](README.ko.md)

## Recover the context your AI forgot.

Agentic Autobiography is a local-first Codex plugin for hackathon demos. It scans source files and recent local activity, recovers forgotten project context, writes a source-grounded 24-hour journal, and renders a dashboard that Codex users can open during a demo.

The Korean dashboard is ready for today's hackathon:

```bash
python3 scripts/agentic_autobiography.py journal --hours 24
python3 scripts/agentic_autobiography.py render-dashboard --lang ko
python3 scripts/agentic_autobiography.py serve --port 8765 --lang ko
```

Open:

```text
http://127.0.0.1:8765/dashboard/
```

## What It Does

- Indexes local Markdown, TXT, JSON, CSV, and best-effort PDF text.
- Scans configurable recent local file activity from the last 24 hours.
- Searches source-grounded context.
- Extracts decisions, timelines, and action items.
- Generates a daily journal with source paths.
- Renders an English or Korean dashboard.
- Exposes MCP tools for Codex plugin integration.

## Codex Plugin

Plugin manifest:

```text
.codex-plugin/plugin.json
```

MCP config:

```text
.mcp.json
```

Available MCP tools:

- `memory.search`
- `memory.timeline`
- `memory.actions`
- `memory.summary`
- `journal.generate`
- `dashboard.render`

## Demo Script

1. Generate the 24-hour journal.
2. Render the Korean dashboard.
3. Open `http://127.0.0.1:8765/dashboard/`.
4. Show that the journal includes summary, timeline, decisions, action items, and source files.
5. Explain the core idea:

> AI should not only answer. It should recover why the answer matters.

## Privacy

By default, the project indexes the included `docs` and `samples` folders. The journal command can also scan configured recent file activity roots from `config/activity_roots.json`.

It does not inspect Gmail, Slack, browser history, Calendar, or Messages unless a future connector is explicitly added and enabled.

## Verification

```bash
python3 -m unittest tests/test_agentic_autobiography.py
.venv/bin/python /Users/m5max/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

## Hackathon Track

RALPHTHON Track 1 - Codex Plugin
