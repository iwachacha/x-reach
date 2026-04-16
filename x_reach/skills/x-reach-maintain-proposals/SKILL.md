---
name: x-reach-maintain-proposals
description: Evaluate proposed changes to X Reach itself as an adoption gate before implementation. Use when Codex receives concrete external proposals, AI review findings, follow-up improvement ideas, or user asks to both judge and safely implement X Reach improvements; review them against topic-agnostic X post collection value, safety, deterministic-before-LLM policy, existing repo surfaces, and handoff quality, then decide adopt_now, adopt_primitives_only, defer, or reject before any edits.
---

# X Reach Maintain Proposals

Review proposed changes to X Reach before code changes.

This is the right maintainer skill when someone has already pasted candidate improvements and asks whether they are worth adopting. It is an adoption gate, not an ideation skill.

Use this skill even when the user also asks for implementation in the same turn: gate first, then implement only the approved slice.

## Workflow

1. Read [../../../docs/project-principles.md](../../../docs/project-principles.md) as the source of current project policy.
2. Read [references/policy-tests.md](references/policy-tests.md) to apply the adoption gate.
3. Read [references/review-output.md](references/review-output.md) to keep the decision record compact and reusable.
4. Inspect the current repo surface before judging overlap. Check `README.md`, `docs/`, `docs/implementation-plan.md`, relevant CLI/runtime modules, schemas, tests, and existing skills when needed.
5. Judge each proposal independently first. Only bundle accepted items when they clearly share one primitive or one release boundary.
6. Split proposals that mix a valuable primitive with risky automation. Use `adopt_primitives_only` when the primitive is worth shipping but the policy layer is not.
7. If the user asked for implementation too, briefly record the gate decision in working notes or docs, then edit only `adopt_now` or `adopt_primitives_only` slices.
8. If implementation is not requested, stop after the decision record.

## Core Rules

- Prefer changes with clear X-specific value for post collection, candidate quality, diagnostics, evidence artifacts, mission specs, or handoff.
- Preserve topic generality. Gourmet, product feedback, incident response, politics, entertainment, OSS, and local events are examples only; do not accept domain-specific defaults unless the caller explicitly supplies them through mission spec, queries, coverage topics, judge intent, or exclude rules.
- Prefer general primitives for theme fit: caller-declared objectives, query terms, coverage topics, deterministic diagnostics, low-content/noise filters, bounded judge contracts, and auditable fallback artifacts.
- X Reach may be more built-out than Agent Reach when the feature is explicit, bounded, observable, and directly improves X post collection.
- Keep caller control. Reject hidden fan-out, unbounded loops, opaque LLM decisions, silent default changes, automatic posting, final interpretation ownership, final selection ownership, and synthesis ownership.
- Apply deterministic before LLM: implement query shaping, dedupe, diagnostics, filters, candidate scoring, diversity constraints, schema, and artifact improvements before considering model judgment.
- LLM or VLM use is acceptable only as an opt-in final judge after deterministic narrowing, with retained reasons and a bounded candidate set.
- Prefer neutral diagnostics, schema clarity, artifact ergonomics, deterministic candidate utility signals, and explicit opt-in controls over invisible policy.
- Reject or defer proposals that duplicate `collect`, `collect --spec`, `doctor`, `channels`, `batch`, `plan candidates`, `ledger`, or existing skill workflows without improving usability.
- When uncertain, choose `defer` if evidence may justify the idea later, or `reject` if it broadens ownership or hides risk.

## Required Gate Checks

For every proposal, verify:

- current repo surface was inspected before judging overlap
- the feature has concrete X-specific value
- the feature improves post collection, candidate quality, diagnostics, artifacts, or handoff
- hidden fan-out, unbounded retries, opaque LLM use, and silent default changes are absent
- deterministic alternatives were considered before LLM/VLM
- topic-specific assumptions were either caller-declared or rejected as hard-coded defaults
- the patch boundary includes tests, docs, diagnostics, and handoff artifacts when needed

## Output

For each proposal, return:

- `decision`: `adopt_now`, `adopt_primitives_only`, `defer`, or `reject`
- `why`: 1-3 sentences tied to X-specific value, safety, and existing surfaces
- `boundary`: smallest safe patch scope if adopted, otherwise `none`
- `touchpoints`: likely files or surfaces
- `verification`: `none`, `targeted`, or `broader`

Do not start editing unless the user also wants implementation or already approved the adopted slice.

## References

- Policy and overlap checks: [references/policy-tests.md](references/policy-tests.md)
- Review record shape: [references/review-output.md](references/review-output.md)
