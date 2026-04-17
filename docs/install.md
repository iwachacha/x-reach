# X Reach Install Guide

This Twitter-only fork keeps the `x-reach` CLI and exposes `x_reach` as the primary Python package, but only ships the `twitter` channel.

## Install the latest fork build

```powershell
uv tool install --force git+https://github.com/iwachacha/x-reach.git
x-reach skill --install
x-reach version
```

To pin a specific build:

```powershell
uv tool install --force git+https://github.com/iwachacha/x-reach.git@<commit-or-ref>
x-reach skill --install
x-reach version
```

## Local install from source

```powershell
uv tool install .
x-reach install --env=auto --channels=twitter
```

## Preview mode

```powershell
x-reach install --env=auto --safe --channels=twitter
x-reach install --env=auto --dry-run --json --channels=twitter
```

The installer only automates these steps:

- `uv tool install twitter-cli`
- `x-reach skill --install`

## Authentication

Twitter/X is cookie-based:

```powershell
x-reach configure twitter-cookies "auth_token=...; ct0=..."
x-reach doctor --json --probe
```

You can also import cookies from a local browser:

```powershell
x-reach configure --from-browser chrome
```

Environment-only execution is supported too:

```powershell
$env:TWITTER_AUTH_TOKEN = "..."
$env:TWITTER_CT0 = "..."
```

Use `doctor --json --probe` before depending on Twitter/X search in downstream automation. `twitter status` confirms authentication, but it does not guarantee that live search still works.

## Integration discovery

```powershell
x-reach channels --json
x-reach doctor --json
x-reach doctor --json --require-channel twitter
x-reach doctor --json --require-all
x-reach doctor --json --probe
x-reach export-integration --client codex --format json
x-reach export-integration --client codex --format json --profile runtime-minimal
```

## Read-only collection smoke commands

```powershell
x-reach search "OpenAI" --limit 5 --json
x-reach hashtag "OpenAI" --limit 5 --json
x-reach collect --operation search --input "OpenAI" --limit 5 --json
x-reach collect --operation search --input "OpenAI" --min-likes 100 --min-views 10000 --json
x-reach collect --operation user --input "openai" --json
x-reach posts "openai" --limit 20 --originals-only --json
x-reach collect --operation user_posts --input "openai" --limit 20 --json
x-reach posts "openai" --limit 20 --min-likes 10 --topic-fit topic-fit.json --json
x-reach collect --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
x-reach collect --operation search --input "OpenAI" --limit 5 --since 2026-01-01 --until 2026-12-31 --json
```

## Ledger diagnostics

```powershell
x-reach collect --operation search --input "OpenAI" --limit 5 --json --save-dir .x-reach/shards --run-id external-run --intent discovery --query-id twitter-openai --source-role social_search
x-reach ledger merge --input .x-reach/shards --output .x-reach/evidence.jsonl --json
x-reach ledger validate --input .x-reach/evidence.jsonl --json
x-reach ledger summarize --input .x-reach/evidence.jsonl --json
x-reach ledger query --input .x-reach/evidence.jsonl --filter "channel == twitter" --fields channel,query_id,result.items[*].url --json
x-reach ledger append --input live-results/twitter-openai.json --output .x-reach/evidence.jsonl --run-id external-run --json
```

