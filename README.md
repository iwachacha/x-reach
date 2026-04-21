# X Reach

X Reach is the X/Twitter-only split of the Windows-first Agent Reach fork. It keeps the same `x-reach` CLI, evidence ledger helpers, and Codex skill suite shape, but removes every non-Twitter channel and makes `x_reach` the primary Python SDK surface.

Its design center is agent-assisted, reproducible X collection: stable JSON contracts, deterministic noise reduction, resumable mission runs, and compact handoff artifacts. The detailed decision criteria live in [docs/project-principles.md](docs/project-principles.md).

## What stays the same

- `x-reach channels --json`
- `x-reach doctor --json`
- `x-reach doctor --json --probe`
- `x-reach collect --operation <op> --input <value> --json`
- `x-reach collect --spec mission.json --output-dir .x-reach/missions/<run> --json`
- `x-reach schema collection-result --json`
- `x-reach schema mission-spec --json`
- `x-reach schema judge-result --json`
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
x-reach --help
x-reach channels --json
x-reach doctor --json
x-reach doctor --json --probe
x-reach search "OpenAI" --limit 5 --json
x-reach search "AI agent" --limit 5 --quality-profile precision --json
x-reach hashtag "OpenAI" --limit 5 --json
x-reach collect --operation search --input "OpenAI" --limit 5 --json
x-reach collect --operation search --input "OpenAI" --min-likes 100 --min-views 10000 --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/openai-research --dry-run --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/openai-research --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/openai-research --concurrency 2 --query-delay 1 --throttle-cooldown 30 --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/openai-research --resume --json
x-reach collect --operation user --input "openai" --json
x-reach posts "openai" --limit 20 --json
x-reach posts "openai" --limit 20 --min-likes 10 --min-views 1000 --topic-fit topic-fit.json --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --sort-by quality_score --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --topic-fit topic-fit.json --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --min-seen-in 2 --json
x-reach collect --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
```

## CI and smoke

Pull requests and pushes run `.github/workflows/pytest.yml` as the required CI gate. It keeps three pillars live: `ruff check`, scoped `mypy` over the contract-bearing `x_reach/` modules, and `pytest`.

Those gates are intended to protect the stable public surface: `x-reach --help`, `x-reach channels --json`, `x-reach doctor --json`, `x-reach doctor --json --probe`, the packaged schema commands, and `x-reach plan candidates --input ... --json`.

`.github/workflows/x-reach-smoke.yml` is a manual observational workflow, not a required release gate. It always captures `channels --json`, `doctor --json`, ledger summary, and candidate-planning artifacts. Live `doctor --json --probe` and `collect` are soft-fail observational checks because auth state and Twitter/X runtime behavior can vary outside the repository.

## CLI Layout

The public CLI contract stays the same, but the implementation now lives under `x_reach/cli/`:

- `x_reach/cli/main.py` keeps `main()` thin
- `x_reach/cli/__main__.py` preserves `python -m x_reach.cli`
- `x_reach/cli/parser.py` builds the parser and registers subcommands
- `x_reach/cli/commands/*.py` holds command handlers
- `x_reach/cli/renderers/*.py` holds human-readable text rendering

`agent_reach.cli` remains a compatibility wrapper that resolves to the primary `x_reach.cli` package.

## Caller-control policy

- X Reach does not choose final investigation scope, final selection, synthesis, scheduling, or publishing.
- X Reach is topic-agnostic: examples such as restaurant research, product feedback, incident reports, creator discourse, or OSS adoption are only examples. Do not hard-code domain-specific assumptions into runtime defaults.
- Collection quality means preserving caller-defined scope while reducing off-topic posts, thin content, duplicates, obvious spam/promotion, and other auditable noise through explicit, inspectable controls.
- Collection-only or raw-evidence handoff is a first-class outcome. Do not force synthesis when the caller wants high-signal posts, ledgers, or machine-readable artifacts.
- The caller chooses scope. Keep lightweight asks lightweight instead of trying to auto-escalate them into large-scale research.
- `x-reach collect --json` is the default thin interface for downstream collection.
- `x-reach collect --spec` is the preferred declarative interface for broad, resumable, artifact-heavy X research runs.
- Broad discovery operations (`search`, `hashtag`, `posts`) default to `quality_profile=balanced`, `raw_mode=none`, and `item_text_mode=snippet` so saved artifacts stay compact unless the caller explicitly opts into fuller payloads.
- `batch` and `scout` are explicit opt-in helpers. They are not the default route for everyday collection.
- Inspect `x-reach channels --json` `operation_contracts` before choosing `since` or `until`.
- `x-reach plan candidates` keeps its default `--limit 20`; raise it only when the caller explicitly wants a wider candidate review set.
- `x-reach plan candidates --json` includes deterministic `quality_score` and `quality_reasons` for review, but it does not make the caller's final selection.
- `x-reach plan candidates --sort-by quality_score` is explicit opt-in utility ordering; the default remains first-seen order for compatibility.
- `x-reach plan candidates --topic-fit topic-fit.json` applies caller-declared deterministic topic-fit rules and emits compact `topic_fit` match/drop diagnostics. When topic-fit rules are active, they take priority over the older query-token match fallback.
- `x-reach posts` and `collect --operation user_posts` support caller-declared `--min-likes`, `--min-retweets`, `--min-views`, and `--topic-fit` filters as client-side timeline filters; they do not add search-tab semantics or hidden author expansion.
- For broad multi-query discovery, `x-reach plan candidates --min-seen-in 2` is an optional way to keep candidates that resurfaced across multiple sightings. Leave it unset for narrow or one-off collection.
- Saved evidence stays quiet by default; add `--warn-missing-evidence-metadata` only when provenance completeness matters for CI or downstream workflows.
- For large-scale research, use a two-stage flow: compact discovery first, then `plan candidates` with `--max-per-author 2 --prefer-originals --drop-noise` before any deeper reads; add `--sort-by quality_score` only when utility-sorted review is useful.
- Quality filtering exposes `quality_filter.dropped_samples` diagnostics so filter thresholds can be audited from a small sample of dropped posts.
- `plan candidates --drop-noise` and mission `exclude.drop_low_content_posts` remove obvious low-content quote posts before ranking.
- For declarative large-scale X collection, use `collect --spec`: it runs a mission plan, writes raw/canonical/ranked artifacts, and leaves a manifest for resumable handoff.
- For broad runs that use `--concurrency > 1`, add explicit pacing such as `--query-delay 1 --throttle-cooldown 30`; throttle-sensitive 409/429/conflict errors are reported in diagnostics and can trip the bounded throttle guard instead of continuing to start every remaining query.
- Mission `coverage` is opt-in and fills only explicit topic gaps; ranked-count gaps are reported but do not trigger automatic query expansion.
- Mission `topic_fit` lets the caller declare required, preferred, exact, negative, and synonym-based topic-fit rules. X Reach uses only those rules for deterministic filtering and diagnostics; it does not infer domain-specific truth or importance.
- Mission `judge` is an opt-in forward-compatible contract. Until a judge runner is configured, it writes auditable fallback records and leaves deterministic `ranked.jsonl` unchanged.

## Docs

- Project principles: [docs/project-principles.md](docs/project-principles.md)
- Improvement plan: [docs/improvement-plan.md](docs/improvement-plan.md)
- Install guide: [docs/install.md](docs/install.md)
- Downstream usage: [docs/downstream-usage.md](docs/downstream-usage.md)
- Codex integration: [docs/codex-integration.md](docs/codex-integration.md)
- Python SDK: [docs/python-sdk.md](docs/python-sdk.md)
- Mission spec runtime: [docs/mission-spec.md](docs/mission-spec.md)
- Compatibility shim policy: [docs/compatibility-shim.md](docs/compatibility-shim.md)
- Troubleshooting: [docs/troubleshooting.md](docs/troubleshooting.md)


