# Codex Integration

This fork keeps the Agent Reach Codex integration surface, but only for Twitter/X collection.

## Install

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git
agent-reach skill --install
```

## Discovery first

```powershell
agent-reach channels --json
agent-reach doctor --json
agent-reach doctor --json --probe
agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 3 --json
agent-reach export-integration --client codex --format json --profile runtime-minimal
```

## Supported channel

- `twitter`

## Policy

- Use these bundled skills only when the user explicitly asks for Agent Reach or names one of them.
- Use native browsing/search instead of Agent Reach for ordinary lightweight web lookups.
- Agent Reach does not choose scope, ranking, summarization, or posting.
- Inspect `operation_contracts` before choosing `since` or `until`.
- Treat `batch` and `scout` as explicit opt-in helpers, not the default path.
