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
- a deterministic mission, ledger, and candidate handoff layer for explicit broad runs

Do not assume this fork owns final interpretation, synthesis, scheduling, publishing, or caller scope.
Do not assume this fork chooses the investigation. The caller chooses scale, time windows, topic assumptions, final selection, synthesis, and posting.

## Operating Rules For Codex

- Do not activate this skill unless the user explicitly asks to use X Reach or names one of its bundled skills. For ordinary lightweight web lookups, use the model's native browsing/search instead.
- Treat X Reach as topic-agnostic. Use caller-declared objectives, queries, coverage topics, judge intent, and exclude rules for theme fit; do not infer hard-coded domain rules from examples.
- Use `x-reach collect --json` as the stable handoff. Preserve the returned `CollectionResult` JSON when another system will rank, summarize, dedupe, or publish it.
- Collection-only or raw-evidence handoff is a valid final deliverable. Do not force a synthesis step when the caller wants posts, ledgers, or machine-readable artifacts.
- When naming channels in prompts or commands, use the exact stable names from `x-reach channels --json`.
- Keep lightweight asks lightweight. Do not auto-escalate a narrow request into large-scale research.
- Use `x-reach collect --spec` for broad, resumable, artifact-heavy runs where one declared mission should own queries, filters, diversity, coverage, and outputs.
- Treat deterministic processing as the default route: query terms, hard filters, dedupe, candidate scoring, and diagnostics before any LLM/VLM judge handoff.
- Inspect `x-reach channels --json` `operation_contracts` before choosing `since` or `until`.
- Use `x-reach collect --json --save .x-reach/evidence.jsonl` when a research run needs one shared evidence ledger.
- Use `x-reach collect --json --save-dir .x-reach/shards` when per-command shards or parallel collection are easier than appending into one file.
- Add `--warn-missing-evidence-metadata` only when provenance completeness matters for the caller or CI checks.
- Merge sharded ledgers with `x-reach ledger merge --input .x-reach/shards --output .x-reach/evidence.jsonl --json` before `ledger summarize`, `ledger query`, or `plan candidates`.
- Use `x-reach plan candidates --input .x-reach/evidence.jsonl --by post --json` for lightweight X post dedupe before selected follow-up reads. Use `--by normalized_url` only when URL-level dedupe is the caller's actual review unit.
- Keep `x-reach plan candidates` at the default `--limit 20` unless the caller explicitly wants a broader candidate set.
- Treat `quality_score`, `quality_reasons`, and `summary.quality_reason_counts` as deterministic evidence-utility diagnostics, not final truth, trust, or publication decisions.
- Use `--min-seen-in 2` only when a broader run benefits from keeping candidates that resurfaced across multiple sightings. Leave it unset for narrow or one-off collection.
- Broad discovery operations default to `quality_profile=balanced`, `raw_mode=none`, and `item_text_mode=snippet`; use `quality_profile=recall` or explicit `--raw-mode full --item-text-mode full` only when fuller payloads are truly needed.
- Use `x-reach schema collection-result --json` when downstream code needs a contract-testable schema.
- Use `x-reach schema judge-result --json` only for opt-in mission judge handoffs; the current runtime writes fallback records and does not call a model.
- Treat `engagement`, `media_references`, `identifiers`, `meta.item_shape`, and `error.category` as diagnostics only. `quality_score` may help review evidence utility, but downstream code or the caller still owns final ranking and selection.
- Treat `batch` and `scout` as explicit opt-in helpers. They are not the default route for everyday collection.
- For large research tasks, only use bounded fan-out when the caller explicitly opts in; then use `plan candidates` for no-model dedupe and deep-read only selected URLs.

## Discovery First

```powershell
x-reach channels --json
x-reach doctor --json
x-reach doctor --json --probe
x-reach schema collection-result --json
x-reach schema judge-result --json
x-reach collect --operation search --input "OpenAI" --limit 5 --json
x-reach search "AI agent" --limit 5 --quality-profile precision --json
x-reach collect --operation search --input "OpenAI" --min-likes 100 --min-views 10000 --json
x-reach collect --operation user --input "openai" --json
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
6. Broad discovery already defaults to compact artifacts; only override with fuller payload modes when the caller explicitly needs them.
7. Prefer `--run-id`, `--intent`, `--query-id`, and `--source-role` on saved evidence.
8. Use diagnostic hints only to explain provenance or extraction shape; downstream code owns ranking and selection.
9. Choose advanced collection controls such as `since` and `until` from the live `operation_contracts`.
10. Treat large-scale research as explicit opt-in. Keep narrow asks on `collect --json` unless the caller clearly wants a broader run.
11. Prefer `collect --spec` when a broad run needs reproducibility, checkpoint/resume behavior, raw/canonical/ranked artifacts, coverage diagnostics, or judge fallback records.
12. Treat Twitter/X as opt-in and cookie-based; authenticated-but-unprobed `warn` means collect may work, but operation readiness is unverified.

## Large-Scale Research Pattern

1. Run `x-reach doctor --json` and inspect `operation_statuses` when readiness matters.
2. Start with 2-4 caller-chosen discovery queries at `--limit 5` to `--limit 10`.
3. Choose `since` and `until` from the live contract instead of assuming a fixed route.
4. Prefer `x-reach collect --spec` when one declared mission can cover the broad run; if a saved batch plan exists, run `x-reach batch --plan PLAN.json --validate-only --json` before the write-producing batch run.
5. Save raw `CollectionResult` envelopes with `--save .x-reach/evidence.jsonl` or `--save-dir .x-reach/shards` when the run needs an evidence trail.
6. If the run produced shards, merge them before summary or candidate planning.
7. Run `x-reach ledger summarize --input .x-reach/evidence.jsonl --json` when CI or downstream automation needs health counts.
8. Run `x-reach plan candidates --input .x-reach/evidence.jsonl --by post --limit 20 --max-per-author 2 --prefer-originals --drop-noise --json` before deeper reads. Inspect `quality_reasons` and `summary.quality_reason_counts`; add `--min-seen-in 2` only when repeated cross-query resurfacing is useful.
9. Return partial results with clear readiness or collection failures instead of hiding them.

## Command Routing

- Social collection: read [references/social.md](references/social.md)

