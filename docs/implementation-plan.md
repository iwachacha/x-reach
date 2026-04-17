# Implementation Plan

Last refreshed: 2026-04-18 JST after caller-declared topic-fit implementation and verification.

This is a maintainer handoff for improving X Reach itself. It records the current project direction, the proposal decisions from `x-reach-review.md`, the runtime evidence gathered during the latest pass, and the next implementation slices. It is a working plan, not a promise to turn X Reach into a final analysis, synthesis, scheduling, or publishing system.

## Current Direction

X Reach should keep deepening as the deterministic X/Twitter evidence runtime that already exists:

- use `x_reach` as the primary runtime and keep `agent_reach` as a thin compatibility shim;
- prefer `collect --spec` for broad, resumable, artifact-heavy X research jobs;
- preserve raw, canonical, and ranked layers as separate machine-readable artifacts;
- improve candidate utility signals, mission diagnostics, and diversity behavior before adding model judgment;
- keep caller intent explicit through queries, time range, language, coverage topics, exclude rules, and judge intent;
- avoid hidden fan-out, unbounded retries, automatic query expansion, domain-specific defaults, final selection, and synthesis ownership.

The policy baseline remains [project-principles.md](project-principles.md): JSON first, mission spec first for broad runs, deterministic before LLM, compact by default, topic-agnostic, and caller-controlled.

## Latest Verification Snapshot

The implementation sequence recorded here began from a clean worktree. The current package version is `1.13.0`.

Live checks run on 2026-04-17 JST:

- `uv run x-reach channels --json`
  - Confirms `twitter` is the only channel.
  - Exposes `search`, `hashtag`, `user`, `user_posts`, and `tweet`.
  - Reports full probe coverage in the channel contract.
- `uv run x-reach doctor --json --probe`
  - `ready=1/1`, `exit_code=0`.
  - Live probes succeeded for all five Twitter operations.
- `uv run x-reach collect --operation search --input "x-reach mission spec" --limit 3 --json`
  - Returned no items, but emitted the expected balanced defaults and unbounded-time-window diagnostics.
- `uv run x-reach collect --operation search --input "OpenAI" --limit 3 --json`
  - Returned three current X posts.
  - Confirmed balanced defaults: `search_type=top`, exclude retweets/replies, raw omitted, snippet item text.
  - Confirmed quality filter diagnostics with `structural_noise` dropped samples.
- `uv run x-reach collect --operation tweet --input "https://x.com/OpenAI/status/2044161906936791179" --limit 3 --json`
  - Confirmed the `tweet` operation can return the seed post plus related thread/reply items.
- A temporary `collect --spec` mission against `OpenAI` with caller-declared `cyber` and `codex` coverage topics completed successfully.
  - Summary: `queries_total=1`, `items_seen=5`, `canonical_items=5`, `ranked_candidates=4`, `filter_drop_counts.low_content=1`.
  - Coverage: no topic gaps, no gap-fill queries, `cyber` and `codex` candidates annotated in `ranked.jsonl`.
  - Judge: `enabled=true` produced `not_run` fallback records with `judge_runner_not_configured`.
- An early temporary mission with `target_posts=2`, coverage disabled, and `diversity.require_topic_spread=true` showed that the field was normalized but not yet backed by an explicit topic-spread stage.
  - Only one candidate survived filtering.
  - Coverage topic gaps were still reported even though coverage gap fill was disabled, which is useful but currently easy to misread.
- This pass then implemented topic-spread enforcement and richer mission diagnostics.
  - `uv run pytest tests/test_mission.py -q --tb=short`: 8 passed.
  - `uv run pytest tests/ -q --tb=short`: 167 passed.
  - `uv run ruff check x_reach/mission.py tests/test_mission.py`: passed.
  - A post-implementation temporary mission confirmed additive `summary.quality_reason_counts`, `summary.topic_spread_status`, `diagnostics.query_yield`, and `diagnostics.curation` fields.
- A follow-up hygiene pass locked the compatibility shim boundary.
  - `uv run pytest tests/test_repo_hygiene.py -q --tb=short`: 8 passed.
  - `uv run pytest tests/ -q --tb=short`: 170 passed.
  - `uv run ruff check tests/test_repo_hygiene.py`: passed.
- The latest implementation pass added the first scoring v2 slice and coverage budget diagnostics.
  - `uv run pytest tests/test_mission.py -q --tb=short`: 10 passed.
  - `uv run pytest tests/ -q --tb=short`: 172 passed.
  - `uv run ruff check x_reach tests`: passed.
  - A post-implementation temporary mission confirmed `query_match`, `strong_query_match`, `engagement_capped`, and `concrete_detail` reasons, plus `coverage.diagnostics` budget fields.
- The current pass extracted the deterministic evidence-utility scoring primitive and reused it from `x-reach plan candidates`.
  - `uv run pytest tests/test_mission.py tests/test_candidates.py -q --tb=short`: 30 passed.
  - `uv run pytest tests/ -q --tb=short`: 175 passed.
  - `uv run ruff check x_reach tests`: passed.
  - A temporary `collect --spec` mission against `OpenAI Codex` completed with `ranked_candidates=4`, `topic_spread_status=already_satisfied`, and shared reasons such as `query_match`, `strong_query_match`, `engagement_capped`, `concrete_detail`, and `thin_quote`.
  - Running `x-reach plan candidates --input <mission>/raw.jsonl --by post --limit 5 --drop-noise --json` on that real mission artifact returned five candidates with `quality_score`, `quality_reasons`, and `summary.quality_reason_counts`.
  - The first verification attempt showed that `coverage.enabled=false` plus `max_queries=0` was rejected. The runtime and schema now accept `max_queries=0` only when coverage gap fill is disabled, while enabled coverage still requires at least one query.
- The bundled workflow review did not justify a new standalone public skill.
  - Instead, `x-reach-orchestrate` now has a focused `mission-spec-flow.md` reference for broad `collect --spec` runs.
  - `x-reach`, `x-reach-orchestrate`, and `x-reach-budgeted-research` now prefer X post candidate review with `--by post --max-per-author 2 --prefer-originals --drop-noise` and explicitly treat `quality_score` / `quality_reasons` as utility diagnostics, not final judgment.
  - Bundled `SKILL.md` frontmatter is now validator-friendly UTF-8 without BOM; all bundled skills pass `quick_validate.py` with `PYTHONUTF8=1`.
  - A dry-run mission matching the new workflow guidance confirmed `coverage.enabled=false`, `coverage.max_queries=0`, `diversity.require_topic_spread=true`, and compact retention normalize together.
  - `uv run pytest tests/test_skill_suite.py -q --tb=short`: 8 passed.
- The latest implementation pass added explicit opt-in quality sorting for `x-reach plan candidates`.
  - `sort_by` now defaults to `first_seen` and is recorded in JSON and human output.
  - `--sort-by quality_score` orders candidates by descending deterministic utility score with stable first-seen tie-breaks.
  - `uv run pytest tests/test_candidates.py tests/test_cli.py -q --tb=short`: 44 passed.
  - `uv run pytest tests/ -q --tb=short`: 179 passed.
  - `uv run ruff check x_reach tests`: passed.
  - A temporary live ledger from `x-reach collect --operation search --input "OpenAI Codex" --limit 8 --quality-profile balanced --json --save <temp-ledger>` confirmed default `sort_by=first_seen`, opt-in `sort_by=quality_score`, and descending quality scores.
- The latest implementation pass added explicit broad-run pacing for `batch` and `collect --spec`.
  - `x-reach batch` and `x-reach collect --spec` now accept `--query-delay`, `--query-jitter`, `--throttle-cooldown`, and `--throttle-error-limit`.
  - Mission specs and batch plans can declare the same controls under `pacing`.
  - Batch/mission diagnostics now include query start/finish, duration, planned/applied waits, error category/retryability, throttle-sensitive flags, wait totals, and throttle-guard status.
  - Plain Twitter/X HTTP 409 conflict and HTTP 429 rate-limit command failures are classified into stable retryable categories.
  - `uv run pytest tests/test_batch.py tests/test_mission.py tests/test_cli.py tests/test_collect_adapters.py tests/test_results.py -q --tb=short`: 70 passed.
  - `uv run pytest tests/ -q --tb=short`: 191 passed.
  - `uv run ruff check x_reach tests`: passed.
  - A temporary live paced mission against `OpenAI Codex` / `OpenAI API` completed with 2/2 queries ok, `waits_applied=1`, `total_wait_seconds=1.0`, and no throttle-sensitive errors.
- The latest implementation pass added caller-declared topic-fit rules.
  - Mission specs now accept `topic_fit` with required-any, required-all, preferred, excluded, exact phrase, negative phrase, and synonym group rules.
  - Mission curation applies active topic-fit rules before the older query-token fallback and reports topic-fit drops, match reasons, and missing required counts in `mission-result.json` and `summary.md`.
  - `x-reach plan candidates --topic-fit PATH.json` applies the same deterministic evaluator and supports `fields=id,quality_score,quality_reasons,topic_fit`.
  - `uv run pytest tests/test_topic_fit.py tests/test_candidates.py tests/test_mission.py tests/test_cli.py -q --tb=short`: 72 passed.
  - `uv run pytest tests/ -q --tb=short`: 204 passed.
  - `uv run ruff check x_reach tests`: passed.

Assessment from the live run:

- The runtime is strongly aligned with current policy: explicit channel contract, reproducible mission artifacts, deterministic filtering, compact defaults, and judge fallback instead of hidden model judgment.
- The biggest remaining usability gaps are now score calibration and `user_posts` parity. Candidate-review ordering has an explicit opt-in quality sort while first-seen order remains the default, broad-run pacing now has explicit controls plus diagnostics, and caller-declared topic-fit rules can replace brittle query-token fallback.
- Candidate ranking and candidate planning now use shared query match strength, caller-declared topic-fit signals, concrete detail markers, capped engagement, post shape, media, URL support, and thin-content penalties. Engagement is still present, but capped and inspectable through `engagement_capped`.
- `diversity.require_topic_spread` now promotes or preserves available caller-declared topic buckets before final truncation. It still cannot rescue topics that were never collected unless coverage gap fill is enabled and has explicit follow-up queries.

## Proposal Decisions

| Area | Decision | Current Status | Next Action |
| --- | --- | --- | --- |
| Compatibility boundary cleanup | `adopt_primitives_only` | Implemented for the current maintenance scope. `agent_reach` Python modules are now tested as wrapper-only shims or explicit SDK alias modules, and public guidance is checked for `x_reach` as the primary Python surface. | Keep the shim until the documented deletion criteria are met; do not remove it in this plan. |
| Deterministic evidence utility scoring | `adopt_now` | Shared primitive implemented for mission ranking and `plan candidates`. Candidate plans now expose `quality_score`, `quality_reasons`, aggregate reason counts, and opt-in `sort_by=quality_score` without making final selections. | Calibrate weights with more representative runs and add broader tests for thin/promo/non-English shapes. |
| Caller-declared topic-fit rules | `adopt_now` | Implemented. Mission specs and `plan candidates --topic-fit` now share deterministic required/preferred/excluded/phrase/synonym matching with compact match/drop diagnostics. Active topic-fit rules take priority over query-token fallback. | Extend the same primitive to `user_posts` parity; do not add domain defaults or model judgment. |
| Bounded second-stage evidence expansion | `defer` | Deferred. `tweet` can fetch thread/reply context manually, but mission does not do hidden seed expansion. | Revisit only after scoring, topic spread, and diagnostics are stronger, and only as an explicit bounded mission option. |
| Topic spread enforcement | `adopt_now` | Implemented in this pass for available caller-declared coverage topics, with diagnostics for applied, already satisfied, and skipped cases. | Add more edge-case tests for unmatched topics and exhausted coverage budgets as coverage diagnostics evolve. |
| Coverage expansion beyond explicit topics | `adopt_primitives_only` | Partially implemented. Explicit topic gap fill exists; ranked-count gaps are report-only, coverage budget diagnostics report queryable gaps/exhaustion/target gaps, and disabled coverage can explicitly use `max_queries=0`. | Keep expansion bounded to declared topics and avoid open-ended expansion. Add clearer wording where users confuse disabled coverage diagnostics with gap fill. |
| Judge runner | `defer` | Contract and fallback records are implemented. External or model runner remains deferred. | Keep fallback as source of truth until deterministic narrowing and observability are stronger. |
| Mission observability | `adopt_now` | Partially implemented. This pass added query-yield rows, quality reason counts, topic-spread diagnostics, author/thread/url concentration, time-spread summaries, and coverage query-budget diagnostics. | Add query duration where available and clearer dropped-sample availability. |
| Broad-run pacing | `adopt_primitives_only` | Implemented. Batch and mission runs now expose explicit query delay, jitter, throttle cooldown, and throttle error limit controls with diagnostics. HTTP 409/429/conflict-style failures can cool down or stop unstarted queries without retrying failed requests. | Calibrate recommended pacing values with representative broad runs; keep retry behavior deferred unless it is explicit, capped, and separately reviewed. |
| Bundled research workflows | `adopt_primitives_only` | Updated existing skills instead of creating a new top-level skill. Added a mission-spec execution workflow reference and aligned candidate-gate guidance with shared scoring. | Keep workflow guidance lean; add a new standalone skill only if repeated use proves a distinct trigger and non-overlapping responsibility. |

## Work Sequence

### Phase 0: Plan Refresh And Runtime Check

Status: completed in this pass.

- Re-read project principles, mission docs, compatibility policy, implementation plan, and review notes.
- Inspected current runtime modules and tests around mission curation, candidate planning, high-signal filtering, coverage, judge fallback, and repo hygiene.
- Ran live `x-reach` channel, doctor, direct collect, tweet collect, and temporary mission checks.
- Updated this document to reflect current status and next handoff.
- Implemented the first runtime slice from this plan: mission diagnostics plus topic-spread enforcement.
- Implemented the compatibility-boundary test slice: wrapper-only shim checks, mirrored schema check, and public-guidance primary-surface check.
- Implemented the first scoring v2 slice and coverage-budget diagnostics without adding hidden model judgment or open-ended query expansion.
- Implemented shared scoring for `plan candidates`, plus live verification on a real mission artifact.
- Updated bundled workflow guidance so agents use mission specs and shared candidate diagnostics correctly without adding a duplicate public skill.
- Implemented broad-run pacing and throttle-guard diagnostics for batch and mission execution, plus guidance for concurrent broad runs.

### Phase 1: Contract Hygiene And Mission Diagnostics

Goal: make current behavior easier to trust before changing ranking behavior.

Status: partially completed in this pass.

Completed:

- Added additive mission JSON diagnostics for query yield, ranked quality reason counts, topic-spread status, author/thread/url concentration, and time spread.
- Added `summary.quality_reason_counts` and `summary.topic_spread_status`.
- Added `Quality Reasons` and `Topic Spread` sections to `summary.md`.
- Added tests for reason-count diagnostics, query-yield diagnostics, topic-spread application, and no-topic skip diagnostics.
- Added tests that prove `agent_reach` Python modules remain wrapper-only shims or explicit SDK alias modules.
- Added repo hygiene checks that public docs, examples, and bundled skills keep `x_reach` as the primary Python surface.
- Added a check that the legacy `agent_reach` collection-result schema mirror stays identical to the `x_reach` schema.

Remaining:

- Add mission diagnostics for query duration, dropped-sample availability, and clearer disabled-coverage wording.
- Keep `summary.md` diagnostic-only; do not turn it into synthesis.

Exit criteria:

- Existing public commands stay unchanged.
- New fields are additive and schema-compatible.
- `summary.md` and `mission-result.json` make it clear when a constraint was requested but could not be applied.
- Targeted tests cover shim hygiene, reason-count summaries, topic-spread diagnostics, disabled-coverage diagnostics, and budget exhaustion diagnostics.

### Phase 2: Evidence Utility Scoring V2

Goal: improve candidate ordering without adding hidden final judgment.

Status: shared mission and candidate-planning implementation completed, including opt-in candidate quality sorting.

Implemented:

- query match strength from caller query tokens;
- substantive text and concrete-detail markers such as numbers, dates, currency, and version-like strings already present in text;
- original/quote/reply/retweet shape with explicit penalties where appropriate;
- multi-sighting and duplicate behavior;
- weak capped engagement diagnostics instead of engagement-dominated ranking;
- media and URL support as modest evidence signals;
- stable `quality_reasons` values and aggregate reason counts in mission outputs.
- thin-content, thin-quote, and promo-language penalties.
- extraction to `x_reach.evidence_scoring` so mission ranking and `plan candidates` use the same deterministic score/reason primitive;
- additive `quality_score`, `quality_reasons`, and `summary.quality_reason_counts` in `plan candidates` output.
- explicit `sort_by=first_seen|quality_score` for `plan candidates`, with first-seen as the default and quality sorting as opt-in utility ordering.

Remaining:

- Calibrate score weights against more representative mission runs.
- Add broader tests for high-engagement thin/promo/quote-shell posts across more item shapes.

Guardrails:

- Do not infer domain-specific importance from examples.
- Do not use LLM/VLM judgment in this phase.
- Do not hide the score. Every meaningful score bump or penalty should leave a compact reason.
- Keep ranked output schema-compatible.

Exit criteria:

- Tests cover low-engagement but substantive posts outranking high-engagement thin posts.
- Tests cover high-engagement thin/promo/quote-shell posts receiving penalties or drops.
- Candidate planning exposes the shared score and reasons while preserving existing order unless the caller opts into `sort_by=quality_score`.
- Mission summaries expose reason distributions so ranking changes are easy to audit.

### Phase 3: Topic Spread And Coverage Clarity

Goal: make caller-declared coverage constraints visible in curated output.

Status: first implementation completed in this pass.

Implemented:

- annotate candidate topic matches before final truncation;
- when topic spread is requested and topics exist, promote or preserve available topic buckets within the final ranked set;
- when topics are absent, unmatched, or unavailable in collected candidates, emit a diagnostic instead of inventing topics;
- allow `coverage.enabled=false` specs to use `max_queries=0` as an explicit no-gap-fill budget while preserving the enabled-coverage minimum of one query.

Remaining:

- keep coverage gap fill tied to explicit topic queries and budgets;
- make ranked-count gaps report-only unless the caller supplies topic queries.
- keep coverage budget diagnostics additive and avoid automatic expansion from target-count gaps.

Exit criteria:

- Topic spread never invents topics.
- Topic spread can change final ordering only to honor caller-declared topic buckets.
- Coverage gap fill remains bounded to `coverage.max_queries` and `coverage.max_rounds=1`.
- Tests cover topic spread success, no-topic diagnostics, unmatched-topic diagnostics, disabled-coverage diagnostics, and exhausted coverage budgets.

### Phase 4: Deferred Design Review

Goal: revisit higher-risk ideas only after the deterministic base is stronger.

Deferred items:

- second-stage evidence expansion from promising seeds;
- external or model-backed judge runner;
- semantic topic detection or multi-round active refinement.

Revisit criteria:

- A fresh proposal gate is recorded before implementation.
- The feature is explicit opt-in through mission spec or CLI.
- Operation contracts validate every new operation and option.
- Budgets, resume behavior, compact retention, diagnostics, and fallback behavior are designed before code changes.
- Deterministic ranked artifacts remain usable when the optional feature is disabled or fails.

## Explicit Non-Goals For This Plan

- Do not remove `agent_reach` in a minor maintenance pass.
- Do not add automatic query expansion from ranked-count gaps.
- Do not add hidden thread, quote, reply, or author deep reads.
- Do not run an LLM/VLM judge before deterministic candidate narrowing.
- Do not bake any domain-specific scoring prompt or noise rule into runtime defaults.
- Do not turn `summary.md` into a final research answer or synthesis.

## Handoff Notes

Start the next implementation pass with `user_posts` parity unless there is a newer maintainer decision. Keep scoring calibration and broader thin/promo/non-English candidate examples in the follow-up queue.

A focused adoption record for the external field-review notes now lives in [field-review-improvement-plan.md](field-review-improvement-plan.md). That plan marks opt-in candidate quality sorting, explicit broad-run pacing, and caller-declared topic-fit as completed; the next safe slice is `user_posts` parity. It explicitly defers automatic `Top` to `Latest` fallback, topic clustering, and VLM/location inference until they pass a fresh proposal gate.

Completed in this pass:

- Implemented mission diagnostics for `quality_reason_counts`, `topic_spread`, query yield, concentration, and time spread.
- Rendered quality reasons and topic spread in `summary.md`.
- Implemented `require_topic_spread=true` for available caller-declared topic buckets.
- Added wrapper-only shim tests and repo hygiene checks for `x_reach` as the primary SDK surface.
- Added mission scoring v2 facets for query match strength, concrete details, capped engagement, post shape, media/URL support, and thin-content penalties.
- Added coverage budget diagnostics for queryable gaps, blocked gap reasons, target gaps, and exhausted query budgets.
- Extracted shared deterministic scoring to `x_reach.evidence_scoring`.
- Added `quality_score`, `quality_reasons`, and `summary.quality_reason_counts` to `plan candidates`.
- Preserved existing `plan candidates` ordering while exposing scores for review.
- Added opt-in `plan candidates --sort-by quality_score`, JSON and human `sort_by` output, stable first-seen tie-breaks, and bundled guidance that treats quality sorting as utility review only.
- Added explicit batch and mission pacing controls, wait/duration diagnostics, Twitter/X HTTP 409/429 classification, and a bounded throttle guard for unstarted queries.
- Allowed disabled coverage specs to use `coverage.max_queries=0`, with enabled coverage still requiring at least one query.
- Added shared deterministic `topic_fit` rules for mission filtering, `plan candidates --topic-fit`, topic-fit match/drop diagnostics, and fallback preservation for `require_query_match`.
- Verified the current behavior with a live `OpenAI Codex` mission and a follow-up `plan candidates` run over the mission `raw.jsonl`.
- Reviewed whether new SKILL/rule/workflow surfaces were warranted. Chose not to add a standalone skill; added `x-reach-orchestrate/references/mission-spec-flow.md` and aligned existing X Reach skills with shared quality scoring and post-level candidate gates.
- Normalized bundled skill frontmatter so the skill-creator validator can read every packaged `SKILL.md`.

Suggested next PR boundary:

- Extend metric filters and optional topic-fit filtering to `user_posts` parity.
- Add more tests for high-engagement thin quotes, promo language, unmatched query tokens, non-English text shapes, and live-run calibration examples.
- Revisit dropped-sample availability and score calibration before considering any second-stage evidence expansion.
