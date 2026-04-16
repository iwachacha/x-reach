# Policy Tests

Use these checks before adopting any X Reach proposal.

## Fast Accept Signals

- The change has direct X-specific value for collecting, filtering, deterministic candidate scoring, diagnosing, or handing off posts.
- The change improves theme-fit quality without hard-coding one research domain into defaults.
- The change makes existing collection behavior easier to inspect through neutral metadata, diagnostics, schemas, or artifacts.
- The change is explicit opt-in, bounded, resumable, and observable.
- The change removes repeated maintainer friction without inventing hidden workflow policy.
- The change implements deterministic filters, query shaping, candidate scoring, diversity constraints, diagnostics, or ledger ergonomics before relying on LLM/VLM judgment.

## Fast Reject Signals

- The feature silently chooses caller scope, expands queries, deep-reads, retries, synthesizes, posts, publishes, or chooses final selection on behalf of the caller.
- The feature bakes a topic-specific assumption into general runtime behavior, such as treating restaurant, product, event, political, OSS, or media-discourse terms as universal defaults.
- The feature adds hidden fan-out, unbounded loops, opaque LLM decisions, or silent default changes.
- The feature normalizes impact, trust, recommendation, final importance, or final meaning in a way that hides raw signals.
- The feature duplicates `collect`, `collect --spec`, `batch`, `plan candidates`, `ledger`, or existing skills without reducing user friction.
- The feature requires broad cross-project behavior but lacks tests, docs, diagnostics, and handoff artifacts.

## Split-When-Possible Rule

If a proposal contains both:

- a useful primitive
- and a risky policy or automation layer

return `adopt_primitives_only`. Keep the primitive and reject or defer the policy layer.

Examples:

- Keep dropped-post diagnostics or auditable quality reasons, reject opaque final importance scoring.
- Keep opt-in coverage topics, reject automatic open-ended query expansion.
- Keep deterministic low-content filtering, defer LLM semantic judgment until candidates are narrowed.
- Keep a generic judge result schema, reject domain-specific judge prompts baked into runtime defaults.

## Overlap Checks

Before adopting, search whether the repo already provides the idea through:

- `x-reach collect --json`
- `x-reach collect --spec`
- `x-reach doctor --json`
- `x-reach channels --json`
- `x-reach batch`
- `x-reach plan candidates`
- `x-reach ledger *`
- `x-reach schema collection-result --json`
- `x-reach schema mission-spec --json`
- `x-reach export-integration --client codex --format json`
- bundled skills under `x_reach/skills`

Also search for topic-overfit risks in docs, tests, and examples. Topic-specific fixtures are fine when they are clearly examples; public guidance and runtime defaults must stay theme-neutral.

If a close surface already exists, prefer extending that surface instead of creating a parallel command or mode.

## LLM/VLM Gate

LLM or VLM proposals are defer-by-default unless all of these are true:

- deterministic narrowing already exists
- model work is opt-in and bounded to a small candidate set
- output includes reasons, confidence, and enough raw evidence for audit
- failures degrade to the deterministic result
- provider/model selection can be changed without rewriting the workflow

## Decision Bias

When the tradeoff is ambiguous, bias toward:

- `adopt_now` only when the patch is local, explicit, observable, and clearly improves X post collection
- `adopt_primitives_only` when the useful primitive can ship without the risky policy layer
- `defer` when evidence is promising but boundaries, cost, or model behavior need more proof
- `reject` when the proposal hides policy, duplicates existing surfaces, or weakens caller control
