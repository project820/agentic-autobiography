# Architecture

```text
Codex
  |
  | MCP tool call / skill prompt
  v
Agentic Autobiography plugin
  |
  | index/search/journal/render
  v
Local memory store
  |
  | source-grounded excerpts
  v
Dashboard + journal artifacts
```

## Components

- `scripts/agentic_autobiography.py`: dependency-free CLI and core engine.
- `scripts/contextos_mcp.py`: minimal stdio MCP server that exposes memory and journal tools.
- `skills/contextos/SKILL.md`: Codex skill instructions.
- `data/index.json`: local document chunks and source metadata.
- `data/journals/*.json`: generated journal entries.
- `dashboard/index.html`: rendered dashboard.

## Data Model

Each indexed chunk contains:

- `id`
- `source`
- `title`
- `modified_at`
- `excerpt`
- `keywords`

Each journal contains:

- `date`
- `generated_at`
- `hours`
- `summary`
- `timeline`
- `decisions`
- `actions`
- `sources`

## Boundaries

The MVP intentionally avoids private integrations. It scans configured local folders and recent file metadata only. Gmail, Messages, browser history, Calendar, and Slack belong in future connector work with explicit user approval.
