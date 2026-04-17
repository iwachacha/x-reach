# Field Review Improvement Plan

Last refreshed: 2026-04-17 JST after the opt-in `plan candidates` quality-sort implementation.

This document records which field-review ideas are worth adopting into X Reach now, which useful primitives should be split away from risky automation, and which ideas should remain deferred or rejected. It complements [implementation-plan.md](implementation-plan.md) and keeps the same policy baseline from [project-principles.md](project-principles.md).

## Policy Baseline

Adopt only changes that improve X post collection, candidate quality, diagnostics, artifacts, or handoff while keeping caller intent explicit and machine-readable.

The following remain guardrails for every patch in this plan:

- no hidden fan-out, unbounded retries, silent default changes, or automatic scope expansion;
- no LLM or VLM judgment before deterministic narrowing;
- no topic-specific defaults for restaurants, Tokyo, products, incidents, OSS, entertainment, or any other domain;
- every new public behavior must be explicit, bounded, observable, and schema-aware;
- existing raw, canonical, ranked, judge, and ledger layers must remain usable when optional features are disabled.

## Current Surface Read

The repo already contains several pieces that make the review suggestions safer to adopt:

- broad operations default to `quality_profile=balanced`, oversample, and expose quality filter diagnostics;
- `search` and `hashtag` support `search_type`, time bounds, language, `min_likes`, `min_retweets`, `min_views`, and query-token diagnostics;
- `user_posts` is treated as a broad operation, but it only exposes `originals_only` and `quality_profile`;
- mission runs already produce raw, canonical, ranked, summary, result, state, and optional judge fallback artifacts;
- ranked candidates and `plan candidates` now share deterministic `quality_score` and `quality_reasons`;
- `plan candidates` preserves first-seen order by default for compatibility and now supports explicit `sort_by=quality_score` utility ordering;
- UTF-8 handling is already present in CLI printing, adapter subprocesses, JSONL writing, and spec loading, so the encoding finding needs a concrete reproduction before a runtime rewrite;
- 429 and retryable error categories exist in result taxonomy, but mission and batch execution do not yet provide explicit pacing controls for large X runs.

## Adoption Decisions

| Proposal | Decision | Why | Smallest safe boundary | Not adopted | Verification |
| --- | --- | --- | --- | --- | --- |
| Opt-in quality ordering for `plan candidates` | `implemented` | The score already exists, the current order was a known review gap, and an opt-in sort improves handoff without changing default compatibility. | Added candidate planner `sort_by` with default `first_seen`; exposed CLI `--sort-by first_seen|quality_score`; sort by descending score only when requested, with stable first-seen tie-breaks. | No default reordering and no final selection claim. | Targeted candidate/CLI tests, full suite, ruff, and live X Reach ledger check passed. |
| Explicit broad-run pacing / safe mode primitive | `adopt_primitives_only` | Field runs hitting 429 directly hurt broad mission reliability. The useful part is bounded, inspectable pacing; the risky part is hidden adaptive automation. | Add explicit mission or batch execution controls for between-query delay, optional jitter, and bounded rate-limit handling. Record planned and applied waits plus retryable errors in diagnostics. | No hidden default safe mode, no indefinite backoff, no automatic query reduction or expansion. | Broader mission/batch tests with injected sleeper and fake rate-limit results; no live dependency required. |
| Caller-declared topic-fit rules | `adopt_now` | Review correctly identifies that query-token substring matching is too thin. A generic caller-declared rule layer improves theme fit without locking the runtime to one domain. | Add deterministic rules such as `required_any_terms`, `required_all_terms`, `preferred_terms`, `excluded_terms`, `exact_phrases`, `negative_phrases`, and `synonym_groups` to mission filtering and candidate analysis. Emit compact match/drop reasons. | No built-in domain synonym packs and no model-based semantic matching in this phase. | Broader tests across English/Japanese text, synonyms, required terms, negative terms, and query-token fallback. |
| `user_posts` quality parity | `adopt_now` | Codex and users can reach a topic through account timelines; that path should not have weaker quality controls than search. | Extend `user_posts` through adapter, SDK, CLI, channel contract, and batch validation with client-side `min_likes`, `min_retweets`, `min_views`, plus optional caller-declared topic-fit rules when the rule layer exists. | No search-only `search_type` semantics and no hidden author deep reads. | Targeted adapter, CLI, contract, and batch tests. |
| Soft-rescue filter buckets | `adopt_primitives_only` | The current quality fallback rescues only engagement misses. More useful boundary candidates can be preserved if hard drops and soft misses are separated. | After topic-fit rules land, classify hard drops such as retweets, replies, promo, and structural noise separately from soft misses such as low engagement, low content, or weak query fit. Keep rescue bounded by requested limit and expose reasons. | No opaque final importance score and no LLM rescue. | Representative filter tests with thin quote, promo, non-English, low-engagement concrete evidence, and weak query-fit examples. |
| Encoding display robustness | `defer` | The codebase already uses UTF-8 subprocess, printing, JSONL, and spec handling. The local review still warrants a guard, but not a broad rewrite without reproduction. | Add a focused regression only when a failing CLI path is identified; otherwise keep troubleshooting guidance around terminal encoding. | No UTF-8-SIG output default and no changing JSON encoding contracts. | Targeted test only if a concrete failing path is reproduced. |
| Automatic `Top` to `Latest` fallback | `defer` | The issue is real, but automatic tab switching would be hidden fan-out and may change result semantics. | Revisit as an explicit caller option only after pacing and diagnostics are stronger, for example a mission query variant that the caller can see before execution. | No default fallback from `top` to `latest`, and no silent extra X calls. | Design review first; tests must prove explicit diagnostics and budget accounting. |
| Topic clustering in ranked artifacts | `defer` | Duplicate-post handling already exists, but semantic clustering by store/topic is hard to make deterministic and topic-neutral. | Consider later as opt-in review grouping in `plan candidates`, using explicit coverage topics, normalized titles, authors, URLs, or caller-supplied entity terms. | No automatic merging of `ranked.jsonl` into opaque topic clusters. | Needs real artifact examples and a separate proposal gate. |
| Tokyo/entity heuristics and VLM location inference | `reject` for defaults, `defer` for opt-in judge use | Hard-coded Tokyo or restaurant heuristics violate topic generality. VLM inference belongs, if ever, behind the existing bounded judge contract after deterministic narrowing. | Use caller-declared coverage topics, query terms, judge criteria, or future opt-in external judge records. | No built-in Tokyo weighting, no domain/poster prior defaults, no VLM in collection filters. | None for rejected defaults; future judge work needs a fresh gate. |

## Implementation Sequence

### Phase 1: Candidate Review Ergonomics

Status: completed in this pass.

This patch uses existing `quality_score`, keeps first-seen ordering as the default, and records the selected `sort_by` in JSON and human output. It updated `x_reach/candidates.py`, `x_reach/cli.py`, candidate/CLI tests, downstream docs, bundled X Reach skills, and Codex integration guidance.

Exit criteria:

- default `plan candidates` output order is unchanged;
- `--sort-by quality_score` returns higher-scored candidates first with stable tie-breaks;
- JSON output records the selected `sort_by`;
- human rendering remains compact and does not imply final judgment.

Verification:

- `uv run pytest tests/test_candidates.py tests/test_cli.py -q --tb=short`: 44 passed.
- `uv run pytest tests/ -q --tb=short`: 179 passed.
- `uv run ruff check x_reach tests`: passed.
- Live temporary X Reach ledger check for `OpenAI Codex` returned 8 items; default planning reported `sort_by=first_seen`, opt-in planning reported `sort_by=quality_score`, and quality-sorted candidate scores were descending.

### Phase 2: Mission And Batch Pacing

Add explicit pacing controls for broad runs before any search-tab fallback or active refinement work.

The first acceptable slice is between-query pacing and diagnostics. If bounded retry behavior is added, it must be opt-in, capped by attempt count and wait budget, and visible in result diagnostics. Prefer injected sleeper tests over live X checks.

Exit criteria:

- no default runtime slowdown unless the caller asks for pacing;
- every wait is tied to an explicit query execution and appears in diagnostics;
- rate-limited results remain normal collection-result errors when retries are disabled or exhausted;
- resume behavior does not replay completed queries just because pacing changed.

### Phase 3: Caller-Declared Topic Fit

Replace the next layer of brittle query-token matching with deterministic caller-declared fit rules.

This should be a general primitive that works for local events, product feedback, incidents, OSS, entertainment, and other themes without shipping any built-in domain pack. The rule layer should feed both filtering and scoring reasons so callers can inspect why a post survived or was dropped.

Exit criteria:

- all rules are supplied by the caller or mission spec;
- matched and missing rules appear in compact reasons or diagnostics;
- query-token matching remains as a fallback, not as the only signal;
- tests include non-English examples and synonym groups without hard-coding a public domain default.

### Phase 4: `user_posts` Parity

Bring account timeline collection closer to search quality without pretending it is search.

Add metric filters and topic-fit filtering client-side. Keep `originals_only` defaults, avoid search-tab options, and preserve the operation contract shape through `channels --json`, SDK, CLI, batch validation, and tests.

Exit criteria:

- `user_posts` accepts and reports metric filters consistently with broad operation contracts;
- filter diagnostics explain before/after counts;
- optional topic-fit rules work on post text, author metadata, quoted author metadata, and URLs;
- existing shortcut behavior remains backward compatible.

### Phase 5: Filter Calibration And Soft Rescue

After the rule layer and `user_posts` parity exist, calibrate hard-drop and soft-rescue behavior with representative artifacts.

This phase should not add model judgment. It should make deterministic filtering less brittle while leaving enough diagnostics for callers to audit the tradeoff.

Exit criteria:

- hard drops and soft misses are separately counted;
- bounded rescue can keep useful borderline posts without hiding why they were borderline;
- high-engagement thin or promo posts do not outrank low-engagement concrete evidence simply because they are popular;
- mission and candidate summaries show reason distributions.

## Deferred Review Queue

These ideas may become useful later but should not be implemented from this plan without a fresh proposal gate:

- explicit multi-search-type query variants after pacing diagnostics exist;
- opt-in topic grouping for candidate review after real artifact examples show stable grouping rules;
- external, LLM, or VLM judge runners after deterministic narrowing, schema fallback, and score calibration are stronger;
- domain-specific entity priors supplied by the caller for one mission, never as global defaults.

## Immediate Handoff

Phase 1 is complete. Move next to explicit pacing, because it addresses the field-run 429 friction without adopting hidden automation. Do not implement `Top` to `Latest` fallback, topic clustering, or VLM location inference until their safe primitive boundaries have been re-reviewed.
