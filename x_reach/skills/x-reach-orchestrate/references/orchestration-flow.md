# Orchestration Flow

## Default Path

1. Determine whether the ask is already executable.
2. If not, shape it into the fixed brief.
3. If channel surface or option support is unclear, run `x-reach channels --json`.
4. If readiness matters, run `x-reach doctor --json`.
5. Use `x-reach doctor --json --probe` only when a live operation check would change the route.
6. Start collection with one or a small number of `x-reach collect --json` commands using the exact stable channel name from `x-reach channels --json`.
7. Synthesize results with source links and explicit uncertainty notes.

## Narrow Research

- stay on `collect --json`
- avoid evidence ledgers unless the user explicitly wants saved provenance
- prefer one to a few targeted Twitter/X commands

## Broad Research

- start with 2-4 small discovery queries
- choose an explicit artifact budget before collection starts
- for machine-readable discovery handoffs, prefer `--raw-mode minimal|none`, `--item-text-mode snippet|none`, and a small `--item-text-max-chars`
- prefer `--save-dir .x-reach/shards` when multiple discovery commands will run, then merge before downstream ledger work
- run `x-reach ledger merge --input .x-reach/shards --output .x-reach/evidence.jsonl --json` before summary, query, or candidate planning
- run `x-reach ledger summarize --input .x-reach/evidence.jsonl --json` when downstream automation needs neutral artifact health counts
- run `x-reach plan candidates --input .x-reach/evidence.jsonl --by normalized_url --limit 20 --json`
- use `x-reach batch --plan PLAN.json --validate-only --json` before any saved batch execution

## Collection-Start Guardrails

- inspect live `operation_contracts` before using `since` or `until`
- treat `engagement`, `media_references`, `identifiers`, and `error.category` as diagnostics only
- keep channel choice task-driven and live-contract-aware

