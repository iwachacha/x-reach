# Implementation Plan

This plan records the maintainer decision after reviewing `x-reach-review.md` against [project-principles.md](project-principles.md) with the updated `x-reach-maintain-proposals` adoption gate. It is a working implementation guide, not a promise to expand X Reach into a final analysis system.

The near-term direction is to deepen the deterministic X evidence runtime that already exists: better candidate utility signals, clearer diversity behavior, stronger mission diagnostics, and sharper shim boundaries. Deferred ideas remain deferred until they can satisfy caller-control, deterministic-before-LLM, and compact-artifact rules.

## Proposal Decisions

### Compatibility Boundary Cleanup

- `proposal`: clarify `x_reach` as runtime and `agent_reach` as shim
- `decision`: `adopt_primitives_only`
- `why`: The current compatibility policy already says `agent_reach` is a shim, and the wrapper modules are intentionally thin. The useful next slice is not removal; it is stronger hygiene that prevents new logic, docs, or tests from treating `agent_reach` as the primary surface.
- `boundary`: add or tighten wrapper-only tests, keep migration docs current, and avoid package removal until the documented deletion criteria are met.
- `touchpoints`: `docs/compatibility-shim.md`, shim tests, repo hygiene tests, release notes when behavior changes
- `verification`: `targeted`
- `topic_generality`: `preserved`

### Deterministic Evidence Utility Scoring

- `proposal`: quality scoring v2
- `decision`: `adopt_now`
- `why`: Better candidate utility signals directly improve X post collection quality and fit the project priority order. The accepted slice is deterministic, auditable scoring facets, not hidden final judgment or domain-specific importance.
- `boundary`: extend existing quality reasons with theme-neutral evidence facets such as query match strength, substantive text, concrete detail markers, media/url support, repost/reply/quote shape, and multi-sighting signals; expose reason counts in mission outputs.
- `touchpoints`: `x_reach/high_signal.py`, `x_reach/candidates.py`, `x_reach/mission.py`, collection and mission tests, mission docs
- `verification`: `broader`
- `topic_generality`: `preserved`

### Bounded Second-Stage Evidence Expansion

- `proposal`: mission follow-up reads from promising seeds
- `decision`: `defer`
- `why`: The idea has X-specific value, but it can easily become hidden fan-out or caller-owned routing. It should wait until deterministic scoring and mission observability make seed selection and budgets explicit.
- `boundary`: no automatic deep reads for now. Revisit only as an explicit mission option with operation-contract validation, strict budgets, compact retention, resume behavior, and clear diagnostics.
- `touchpoints`: future mission spec schema, channel operation contracts, `x_reach/mission.py`, tests, docs
- `verification`: `broader`
- `topic_generality`: `caller_declared_only`

### Topic Spread Enforcement

- `proposal`: make `diversity.require_topic_spread` meaningful
- `decision`: `adopt_now`
- `why`: The field is already accepted by mission specs, so leaving it as a weak or no-op signal creates contract ambiguity. Implementing a bounded topic-spread primitive improves curated evidence quality without choosing the caller's final interpretation.
- `boundary`: when caller-declared coverage topics exist and `require_topic_spread=true`, promote or preserve candidates across topic buckets within the ranked output; when topics are absent, report that no topic-spread constraint could be applied.
- `touchpoints`: `x_reach/mission.py`, `x_reach/schema_files/mission_spec.schema.json`, mission docs, mission tests
- `verification`: `targeted`
- `topic_generality`: `caller_declared_only`

### Coverage Expansion Beyond Explicit Topics

- `proposal`: make coverage gap fill stronger
- `decision`: `adopt_primitives_only`
- `why`: Explicit topic gap fill is already aligned with caller control. Automatic broad query expansion from ranked-count gaps would weaken that boundary.
- `boundary`: keep gap fill tied to caller-declared topics; improve diagnostics for target-count gaps, exhausted query budgets, and unmatched topics. Do not add open-ended or model-generated query expansion.
- `touchpoints`: `x_reach/mission.py`, mission docs, mission tests
- `verification`: `targeted`
- `topic_generality`: `caller_declared_only`

### Judge Runner

- `proposal`: minimal external or model judge runner
- `decision`: `defer`
- `why`: The schema-first judge fallback is useful today, but actual LLM/VLM judging should come after deterministic narrowing, diagnostics, and topic-spread behavior are stronger. This avoids making model output look like the source of truth.
- `boundary`: keep the existing judge contract and fallback records. Revisit an explicit external JSONL runner only after accepted deterministic work lands, with bounded candidates, retained reasons, provider-agnostic configuration, and fallback to ranked output.
- `touchpoints`: future judge runner docs, schema tests, `x_reach/mission.py`, CLI options
- `verification`: `broader`
- `topic_generality`: `caller_declared_only`

### Mission Observability

- `proposal`: improve job diagnostics and summary signals
- `decision`: `adopt_now`
- `why`: Observability makes collection behavior easier to inspect without adding hidden policy. It supports broad runs, debugging, and downstream handoff while preserving caller control.
- `boundary`: add neutral counts and summaries for query yield, filter drops, quality reason distribution, author/thread/url concentration, coverage topic counts, and time spread where the data is already available.
- `touchpoints`: `x_reach/mission.py`, `x_reach/candidates.py` if shared summaries are needed, mission docs, mission tests
- `verification`: `targeted`
- `topic_generality`: `preserved`

## Work Sequence

### Phase 1: Contract Hygiene And Diagnostics

Goal: remove ambiguity before changing scoring behavior.

- Add tests that confirm `agent_reach` modules remain wrappers around `x_reach` modules.
- Add a repo hygiene check that docs and examples keep `x_reach` as the primary SDK surface.
- Document any intentional compatibility exceptions in `docs/compatibility-shim.md`.
- Add mission summary diagnostics for currently available counts: query yield, filter drops, quality reasons, author/thread/url diversity drops, coverage gaps, and judge fallback use.

Exit criteria:

- Existing public commands stay unchanged.
- New diagnostics are additive JSON fields or summary text.
- Targeted tests cover shim hygiene and mission summary diagnostics.

### Phase 2: Evidence Utility Scoring V2

Goal: improve candidate ordering without adding hidden judgment.

- Extend deterministic quality facets in the existing high-signal and candidate paths.
- Keep engagement as a weak diagnostic, not the primary quality signal.
- Add stable `quality_reasons` values for the new facets.
- Update mission summaries to show reason distribution, so scoring changes are inspectable.

Exit criteria:

- Ranked output remains schema-compatible.
- Reasons explain why a candidate moved up or down.
- Tests cover topic-neutral examples, including low-engagement but substantive posts and high-engagement thin posts.

### Phase 3: Topic Spread And Coverage Clarity

Goal: make caller-declared coverage constraints visible in curated output.

- Implement `diversity.require_topic_spread` only against caller-declared coverage topics.
- Add diagnostics when topic spread is requested without usable topics.
- Keep ranked-count gaps report-only unless the caller supplies explicit coverage queries.
- Improve coverage budget reporting.

Exit criteria:

- Topic spread never invents topics.
- Coverage gap fill remains bounded to explicit caller-declared topics and query budgets.
- Mission tests cover topic spread success, no-topic diagnostics, and exhausted coverage budgets.

### Phase 4: Deferred Design Review

Goal: revisit higher-risk ideas after the deterministic base is stronger.

- Re-evaluate second-stage evidence expansion as an explicit mission option, not automatic fan-out.
- Re-evaluate an external judge runner after deterministic scoring and topic spread are stable.
- Require a fresh proposal gate before implementing either feature.

Exit criteria:

- No implementation starts without a new adoption record.
- Any accepted design includes budgets, operation-contract validation, resume behavior, compact retention, and fallback behavior.

## Explicit Non-Goals For This Plan

- Do not remove `agent_reach` in a minor maintenance pass.
- Do not add automatic query expansion from ranked-count gaps.
- Do not add hidden thread, quote, reply, or author deep reads.
- Do not run an LLM/VLM judge before deterministic candidate narrowing.
- Do not bake any domain-specific scoring prompt or noise rule into runtime defaults.
