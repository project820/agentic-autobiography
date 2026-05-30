# Agentic Autobiography

## Recover the context your AI forgot.

Agentic Autobiography is a local-first Codex plugin inspired by ContextOS. It indexes local notes, project logs, PRDs, and recent file activity, then helps Codex recover forgotten context and write a source-grounded daily journal.

It is not a chatbot and not a life-tracking black box. It is a small memory layer for Codex:

- Index local Markdown, TXT, JSON, CSV, and best-effort PDF text.
- Search source-grounded context.
- Extract decisions and action items.
- Generate a 24-hour daily journal.
- Scan configurable recent local file activity from the last 24 hours.
- Render a dashboard for browsing journals and sources.
- Expose MCP tools for Codex integration.

## Install

```bash
git clone <repo-url>
cd "agentic autobiography"
python3 scripts/agentic_autobiography.py index
python3 scripts/agentic_autobiography.py journal --hours 24
python3 scripts/agentic_autobiography.py render-dashboard
python3 scripts/agentic_autobiography.py serve --port 8766
```

Then open:

```text
http://127.0.0.1:8766/dashboard/
```

## Codex Plugin

The plugin manifest lives at:

```text
.codex-plugin/plugin.json
```

The MCP server is configured in:

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

## Typical Use

```bash
python3 scripts/agentic_autobiography.py index --docs docs samples
python3 scripts/agentic_autobiography.py activity --hours 24
python3 scripts/agentic_autobiography.py search "Woori SafeLink decisions"
python3 scripts/agentic_autobiography.py journal --hours 24
python3 scripts/agentic_autobiography.py serve
```

For the required real-time audit loop:

```bash
python3 scripts/three_hour_audit_tick.py --duration-seconds 10800 --interval-seconds 600 --reset
python3 scripts/finalize_audit_report.py
```

The finalizer returns success only after the audit state is `passed`, local verification checks pass, and `origin/main` matches the current `HEAD`. Add `--send-telegram` to send the final report through the existing Hermes Telegram settings.

Example Codex prompt:

```text
@context "What did we decide about the Woori SafeLink project?"
```

## Data

Local generated data is stored under:

```text
data/index.json
data/journals/*.json
dashboard/index.html
```

The index stores excerpts and metadata, not embeddings. This keeps the MVP dependency-free and installable in minutes. The architecture leaves room for a vector database later.

## Privacy

By default, document indexing uses the included `docs` and `samples` folders, while the `journal` command also scans configurable recent local file activity. It does not inspect Gmail, Slack, browser history, Calendar, or Messages unless a future connector is explicitly added and enabled.

Recent activity roots are configured in:

```text
config/activity_roots.json
```

The default roots are `~/Desktop`, `~/Documents`, `~/Downloads`, and `~/.codex/sessions`, with common build/cache/private-heavy folders excluded. You can override this per run:

```bash
python3 scripts/agentic_autobiography.py journal --hours 24 --activity-roots ~/Documents ~/Downloads
```

## Hackathon Track

RALPHTHON Track 1 - Codex Plugin

ContextOS positioning:

> AI does not only need to answer. It needs to remember why the answer matters.
