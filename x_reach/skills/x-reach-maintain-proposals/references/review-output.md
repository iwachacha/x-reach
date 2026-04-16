# Review Output

Use this shape when reporting proposal decisions.

## Per-Proposal Record

- `proposal`: short label
- `decision`: `adopt_now` | `adopt_primitives_only` | `defer` | `reject`
- `why`: concise rationale tied to X-specific value, safety, deterministic-before-LLM policy, and existing repo surfaces
- `boundary`: smallest safe implementation slice, or `none`
- `touchpoints`: files, commands, schemas, docs, skills, or tests likely to change
- `verification`: `none` | `targeted` | `broader`
- `topic_generality`: `preserved` | `caller_declared_only` | `overfit_risk`

## Bundle Rule

Only combine proposals into one implementation group when all of these are true:

- they share one primitive or one release boundary
- they do not mix accepted and deferred policy questions
- they can be explained as one focused patch

Otherwise, keep them separate.

## Implementation Handoff

When at least one proposal is `adopt_now` or `adopt_primitives_only`, hand off only:

- the approved proposal labels
- any rejected policy layer when `adopt_primitives_only` is used
- the explicit patch boundary
- the likely touchpoints
- the expected verification level
- the topic-generality constraint that must remain true during implementation

Do not hand off rejected or deferred ideas as "nice to have" extras.
