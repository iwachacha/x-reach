# Twitter Reach

Twitter Reach is a Twitter-only split of the Windows-first Agent Reach fork. It keeps the same `agent-reach` CLI, Python import surface, evidence ledger helpers, and Codex skill suite shape, but removes every non-Twitter channel.

## What stays the same

- `agent-reach channels --json`
- `agent-reach doctor --json`
- `agent-reach doctor --json --probe`
- `agent-reach collect --channel twitter --operation <op> --input <value> --json`
- `agent-reach schema collection-result --json`
- `agent-reach plan candidates --input .agent-reach/evidence.jsonl --json`
- `agent-reach ledger merge|validate|summarize|query|append`
- `agent-reach export-integration --client codex --format json`
- `from agent_reach import AgentReachClient`

## Current channel surface

Supported channels:

- `twitter`

The live contract is always `agent-reach channels --json`.

## Install the latest fork build

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git
agent-reach skill --install
agent-reach version
```

To pin an exact build:

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git@<commit-or-ref>
agent-reach skill --install
agent-reach version
```

For a source checkout:

```powershell
uv tool install --force .
agent-reach version
```

## Quick flow

```powershell
agent-reach channels --json
agent-reach doctor --json
agent-reach doctor --json --probe
agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json
agent-reach collect --channel twitter --operation user --input "openai" --json
agent-reach collect --channel twitter --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
```

## Caller-control policy

- Agent Reach does not choose investigation scope, ranking, summarization, or publishing.
- The caller chooses scope. Keep lightweight asks lightweight instead of trying to auto-escalate them into large-scale research.
- `agent-reach collect --json` is the default thin interface for downstream collection.
- `batch` and `scout` are explicit opt-in helpers. They are not the default route for everyday collection.
- Inspect `agent-reach channels --json` `operation_contracts` before choosing `since` or `until`.
- `agent-reach plan candidates` keeps its default `--limit 20`; raise it only when the caller explicitly wants a wider candidate review set.

## Docs

- Install guide: [docs/install.md](docs/install.md)
- Downstream usage: [docs/downstream-usage.md](docs/downstream-usage.md)
- Codex integration: [docs/codex-integration.md](docs/codex-integration.md)
- Python SDK: [docs/python-sdk.md](docs/python-sdk.md)
- Troubleshooting: [docs/troubleshooting.md](docs/troubleshooting.md)
