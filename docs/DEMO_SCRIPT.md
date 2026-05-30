# Demo Script

## Goal

Show Codex recovering context and writing a daily agentic autobiography journal.

## Steps

1. Show the plugin manifest and skill.
2. Index sample documents.
3. Ask a ContextOS-style question.
4. Generate a 24-hour journal.
5. Open the dashboard.

## Commands

```bash
python3 scripts/agentic_autobiography.py index --docs samples docs
python3 scripts/agentic_autobiography.py search "What did we decide about Woori SafeLink?"
python3 scripts/agentic_autobiography.py journal --hours 24
python3 scripts/agentic_autobiography.py render-dashboard
python3 scripts/agentic_autobiography.py serve --port 8766
```

## Closing Line

AI already answers questions. ContextOS helps Codex remember why the answer matters.
