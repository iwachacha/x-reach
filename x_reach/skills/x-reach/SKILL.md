---
name: x-reach
description: Windows-first Twitter/X research integration tooling for Codex. Use only when the user explicitly asks to use X Reach or one of its bundled skills, and the task is to inspect Twitter/X capability, verify readiness, export Codex integration settings, or run thin read-only collection over `twitter`.
---

# X Reach

Use this skill only when the user explicitly asks to use X Reach or names this skill. For ordinary lightweight web lookups, use the model's native browsing/search instead of X Reach.

## Positioning

This fork is intentionally narrow. Treat it as:

- a machine-readable channel registry
- a readiness and diagnostics layer
- an integration helper for downstream projects
- a thin read-only Twitter/X collection surface

Do not assume this fork owns scheduling, ranking, summarization, or publishing.
Do not assume this fork chooses investigation scope. The caller chooses scale, time windows, ranking, summarization, and posting.

## Operating Rules For Codex

- Do not activate this skill unless the user explicitly asks to use X Reach or names one of its bundled skills. For ordinary lightweight web lookups, use the model's native browsing/search instead.
- Use `x-reach collect --json` as the stable handoff. Preserve the returned `CollectionResult` JSON when another system will rank, summarize, dedupe, or publish it.
- When naming channels in prompts or commands, use the exact stable names from `x-reach channels --json`.
- Keep lightweight asks lightweight. Do not auto-escalate a narrow request into large-scale research.
- Inspect `x-reach channels --json` `operation_contracts` before choosing `since` or `until`.
- Use `x-reach collect --json --save .x-reach/evidence.jsonl` when a research run needs one shared evidence ledger.
- Use `x-reach collect --json --save-dir .x-reach/shards` when per-command shards or parallel collection are easier than appending into one file.
- Merge sharded ledgers with `x-reach ledger merge --input .x-reach/shards --output .x-reach/evidence.jsonl --json` before `ledger summarize`, `ledger query`, or `plan candidates`.
- Use `x-reach plan candidates --input .x-reach/evidence.jsonl --json` for lightweight URL or ID dedupe before selected follow-up reads.
- Keep `x-reach plan candidates` at the default `--limit 20` unless the caller explicitly wants a broader candidate set.
- Use `x-reach schema collection-result --json` when downstream code needs a contract-testable schema.
- Treat `engagement`, `media_references`, `identifiers`, `extras.source_hints`, `extras.engagement_complete`, `extras.media_complete`, and `error.category` as diagnostics only, not ranking or trust scores.
- Treat `batch` and `scout` as explicit opt-in helpers. They are not the default route for everyday collection.
- For large research tasks, only use bounded fan-out when the caller explicitly opts in; then use `plan candidates` for no-model dedupe and deep-read only selected URLs.

## Discovery First

```powershell
x-reach channels --json
x-reach doctor --json
x-reach doctor --json --probe
x-reach schema collection-result --json
x-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json
x-reach collect --channel twitter --operation user --input "openai" --json
x-reach export-integration --client codex --format json --profile runtime-minimal
```

## Supported Channel

- `twitter`: Twitter/X search through `twitter-cli`

## Workflow

1. Run `x-reach channels --json` if the available surfaces are unclear.
2. Run `x-reach doctor --json` when readiness matters.
3. Inspect `summary.required_not_ready`, `summary.informational_not_ready`, and `summary.probe_attention`.
4. Use `--probe` only when a lightweight live check is useful.
5. Use `x-reach collect --json` by default when external code needs normalized results.
6. For large machine-readable handoffs, prefer `--raw-mode minimal|none` plus `--item-text-mode snippet|none`.
7. Prefer `--run-id`, `--intent`, `--query-id`, and `--source-role` on saved evidence.
8. Use diagnostic hints only to explain provenance or extraction shape; downstream code owns ranking and selection.
9. Choose advanced collection controls such as `since` and `until` from the live `operation_contracts`.
10. Treat large-scale research as explicit opt-in. Keep narrow asks on `collect --json` unless the caller clearly wants a broader run.
11. Treat Twitter/X as opt-in and cookie-based; authenticated-but-unprobed `warn` means collect may work, but operation readiness is unverified.

## Large-Scale Research Pattern

1. Run `x-reach doctor --json` and inspect `operation_statuses` when readiness matters.
2. Start with 2-4 caller-chosen discovery queries at `--limit 5` to `--limit 10`.
3. Choose `since` and `until` from the live contract instead of assuming a fixed route.
4. If a saved batch plan exists, run `x-reach batch --plan PLAN.json --validate-only --json` before the write-producing batch run.
5. Save raw `CollectionResult` envelopes with `--save .x-reach/evidence.jsonl` or `--save-dir .x-reach/shards` when the run needs an evidence trail.
6. If the run produced shards, merge them before summary or candidate planning.
7. Run `x-reach ledger summarize --input .x-reach/evidence.jsonl --json` when CI or downstream automation needs health counts.
8. Run `x-reach plan candidates --input .x-reach/evidence.jsonl --by normalized_url --limit 20 --json` before deeper reads.
9. Return partial results with clear readiness or collection failures instead of hiding them.

## Command Routing

- Social collection: read [references/social.md](references/social.md)

