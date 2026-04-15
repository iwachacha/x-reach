# Agent Reach Install Guide

This Twitter-only fork keeps the `agent-reach` CLI and Python package layout, but only ships the `twitter` channel.

## Install the latest fork build

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git
agent-reach skill --install
agent-reach version
```

To pin a specific build:

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git@<commit-or-ref>
agent-reach skill --install
agent-reach version
```

## Local install from source

```powershell
uv tool install .
agent-reach install --env=auto --channels=twitter
```

## Preview mode

```powershell
agent-reach install --env=auto --safe --channels=twitter
agent-reach install --env=auto --dry-run --json --channels=twitter
```

The installer only automates these steps:

- `uv tool install twitter-cli`
- `agent-reach skill --install`

## Authentication

Twitter/X is cookie-based:

```powershell
agent-reach configure twitter-cookies "auth_token=...; ct0=..."
agent-reach doctor --json --probe
```

You can also import cookies from a local browser:

```powershell
agent-reach configure --from-browser chrome
```

Environment-only execution is supported too:

```powershell
$env:TWITTER_AUTH_TOKEN = "..."
$env:TWITTER_CT0 = "..."
```

Use `doctor --json --probe` before depending on Twitter/X search in downstream automation. `twitter status` confirms authentication, but it does not guarantee that live search still works.

## Integration discovery

```powershell
agent-reach channels --json
agent-reach doctor --json
agent-reach doctor --json --require-channel twitter
agent-reach doctor --json --require-all
agent-reach doctor --json --probe
agent-reach export-integration --client codex --format json
agent-reach export-integration --client codex --format json --profile runtime-minimal
```

## Read-only collection smoke commands

```powershell
agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json
agent-reach collect --channel twitter --operation user --input "openai" --json
agent-reach collect --channel twitter --operation user_posts --input "openai" --limit 20 --json
agent-reach collect --channel twitter --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --since 2026-01-01 --until 2026-12-31 --json
```

## Ledger diagnostics

```powershell
agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json --save-dir .agent-reach/shards --run-id external-run --intent discovery --query-id twitter-openai --source-role social_search
agent-reach ledger merge --input .agent-reach/shards --output .agent-reach/evidence.jsonl --json
agent-reach ledger validate --input .agent-reach/evidence.jsonl --json
agent-reach ledger summarize --input .agent-reach/evidence.jsonl --json
agent-reach ledger query --input .agent-reach/evidence.jsonl --filter "channel == twitter" --fields channel,query_id,result.items[*].url --json
agent-reach ledger append --input live-results/twitter-openai.json --output .agent-reach/evidence.jsonl --run-id external-run --json
```
