# X Reach

X Reach is the X/Twitter-only split of the Windows-first Agent Reach fork. It keeps the same `x-reach` CLI, evidence ledger helpers, and Codex skill suite shape, but removes every non-Twitter channel and makes `x_reach` the primary Python SDK surface.

## What stays the same

- `x-reach channels --json`
- `x-reach doctor --json`
- `x-reach doctor --json --probe`
- `x-reach collect --channel twitter --operation <op> --input <value> --json`
- `x-reach schema collection-result --json`
- `x-reach plan candidates --input .x-reach/evidence.jsonl --json`
- `x-reach ledger merge|validate|summarize|query|append`
- `x-reach export-integration --client codex --format json`
- `from x_reach import XReachClient`

## Current channel surface

Supported channels:

- `twitter`

The live contract is always `x-reach channels --json`.

Legacy compatibility imports such as `from agent_reach import XReachClient` remain available.

## Install the latest fork build

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git
x-reach skill --install
x-reach version
```

To pin an exact build:

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git@<commit-or-ref>
x-reach skill --install
x-reach version
```

For a source checkout:

```powershell
uv tool install --force .
x-reach version
```

## Quick flow

```powershell
x-reach channels --json
x-reach doctor --json
x-reach doctor --json --probe
x-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json
x-reach collect --channel twitter --operation user --input "openai" --json
x-reach collect --channel twitter --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
```

## Caller-control policy

- X Reach does not choose investigation scope, ranking, summarization, or publishing.
- The caller chooses scope. Keep lightweight asks lightweight instead of trying to auto-escalate them into large-scale research.
- `x-reach collect --json` is the default thin interface for downstream collection.
- `batch` and `scout` are explicit opt-in helpers. They are not the default route for everyday collection.
- Inspect `x-reach channels --json` `operation_contracts` before choosing `since` or `until`.
- `x-reach plan candidates` keeps its default `--limit 20`; raise it only when the caller explicitly wants a wider candidate review set.

## Docs

- Install guide: [docs/install.md](docs/install.md)
- Downstream usage: [docs/downstream-usage.md](docs/downstream-usage.md)
- Codex integration: [docs/codex-integration.md](docs/codex-integration.md)
- Python SDK: [docs/python-sdk.md](docs/python-sdk.md)
- Troubleshooting: [docs/troubleshooting.md](docs/troubleshooting.md)


