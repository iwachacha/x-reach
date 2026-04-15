# X Reach

X Reach is the X/Twitter-only split of the Windows-first Agent Reach fork. It keeps the same `x-reach` CLI, evidence ledger helpers, and Codex skill suite shape, but removes every non-Twitter channel and makes `x_reach` the primary Python SDK surface.

## What stays the same

- `x-reach channels --json`
- `x-reach doctor --json`
- `x-reach doctor --json --probe`
- `x-reach collect --operation <op> --input <value> --json`
- `x-reach schema collection-result --json`
- `x-reach plan candidates --input .x-reach/evidence.jsonl --json`
- `x-reach ledger merge|validate|summarize|query|append`
- `x-reach export-integration --client codex --format json`
- `from x_reach import XReachClient`

## Current channel surface

Supported channels:

- `twitter`

The live contract is always `x-reach channels --json`.

## Install the latest fork build

```powershell
uv tool install --force git+https://github.com/iwachacha/x-reach.git
x-reach skill --install
x-reach version
```

To pin an exact build:

```powershell
uv tool install --force git+https://github.com/iwachacha/x-reach.git@<commit-or-ref>
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
x-reach search "OpenAI" --limit 5 --json
x-reach search "AI agent" --limit 5 --quality-profile precision --json
x-reach hashtag "OpenAI" --limit 5 --json
x-reach collect --operation search --input "OpenAI" --limit 5 --json
x-reach collect --operation search --input "OpenAI" --min-likes 100 --min-views 10000 --json
x-reach collect --operation user --input "openai" --json
x-reach posts "openai" --limit 20 --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --min-seen-in 2 --json
x-reach collect --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
```

## Caller-control policy

- X Reach does not choose investigation scope, ranking, summarization, or publishing.
- Collection-only or raw-evidence handoff is a first-class outcome. Do not force synthesis when the caller wants high-signal posts, ledgers, or machine-readable artifacts.
- The caller chooses scope. Keep lightweight asks lightweight instead of trying to auto-escalate them into large-scale research.
- `x-reach collect --json` is the default thin interface for downstream collection.
- Broad discovery operations (`search`, `hashtag`, `posts`) default to `quality_profile=balanced`, `raw_mode=none`, and `item_text_mode=snippet` so saved artifacts stay compact unless the caller explicitly opts into fuller payloads.
- `batch` and `scout` are explicit opt-in helpers. They are not the default route for everyday collection.
- Inspect `x-reach channels --json` `operation_contracts` before choosing `since` or `until`.
- `x-reach plan candidates` keeps its default `--limit 20`; raise it only when the caller explicitly wants a wider candidate review set.
- For broad multi-query discovery, `x-reach plan candidates --min-seen-in 2` is an optional way to keep candidates that resurfaced across multiple sightings. Leave it unset for narrow or one-off collection.
- Saved evidence stays quiet by default; add `--warn-missing-evidence-metadata` only when provenance completeness matters for CI or downstream workflows.
- For large-scale research, use a two-stage flow: compact discovery first, then `plan candidates` with `--max-per-author 2 --prefer-originals --drop-noise` before any deeper reads.

## Docs

- Install guide: [docs/install.md](docs/install.md)
- Downstream usage: [docs/downstream-usage.md](docs/downstream-usage.md)
- Codex integration: [docs/codex-integration.md](docs/codex-integration.md)
- Python SDK: [docs/python-sdk.md](docs/python-sdk.md)
- Troubleshooting: [docs/troubleshooting.md](docs/troubleshooting.md)


