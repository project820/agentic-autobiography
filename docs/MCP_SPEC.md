# MCP Specification

## Server

`agentic-autobiography`

## Tools

### memory.search

Search indexed local context.

Input:

```json
{
  "query": "string",
  "limit": 5
}
```

### memory.timeline

Build a source-grounded timeline for an entity or project.

Input:

```json
{
  "entity": "string",
  "limit": 10
}
```

### memory.actions

Extract unfinished work and follow-up items.

Input:

```json
{
  "scope": "string",
  "limit": 10
}
```

### memory.summary

Generate a recovered context report.

Input:

```json
{
  "query": "string"
}
```

### journal.generate

Write a daily journal from the last N hours of indexed context and recent files.

Input:

```json
{
  "hours": 24,
  "activity_roots": ["~/Documents", "~/Downloads"]
}
```

### dashboard.render

Render the static dashboard.

Input:

```json
{}
```
