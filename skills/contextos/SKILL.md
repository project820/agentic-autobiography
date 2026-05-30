---
name: contextos
description: Recover source-grounded project context, timelines, action items, and daily agentic autobiography journals from local files.
---

# ContextOS / Agentic Autobiography Skill

## Purpose

Use this skill when the user asks Codex to recover forgotten context, summarize recent local work, generate a daily journal, inspect decisions, or open the autobiography dashboard.

This skill is local-first. It reads configured folders, stores a lightweight local index, cites source paths, and avoids claiming context that is not present in sources.

## Commands

From the plugin root:

```bash
python3 scripts/agentic_autobiography.py index
python3 scripts/agentic_autobiography.py search "What changed today?"
python3 scripts/agentic_autobiography.py journal --hours 24
python3 scripts/agentic_autobiography.py render-dashboard
python3 scripts/agentic_autobiography.py serve --port 8766
```

## Codex Behavior

When invoked:

1. Search the local memory index first.
2. Recover who, what, when, why, and next actions.
3. Cite source files for every material claim.
4. Separate observed facts from interpretation.
5. If recent activity is requested, use the last 24 hours unless the user gives another window.
6. If sources are sparse, say so directly and produce a cautious journal.

## Output Format

Use this shape unless the user requests something else:

```md
## Recovered Context

## Timeline

## Decisions

## Action Items

## Sources
```

## Safety Rules

- Never read private integrations such as Gmail, Calendar, Slack, browser history, or Messages unless the user explicitly configures that source.
- Never invent meetings, people, or decisions.
- Prefer absolute local file citations when reporting results.
- Treat the dashboard as a rendered artifact that must be refreshed after journal generation.
