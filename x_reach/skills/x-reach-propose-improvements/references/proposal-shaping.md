# Proposal Shaping

Use this guide when turning external research into X Reach improvement proposals.

## Goal

Produce a short list of proposals that:

- clearly address observed friction
- fit X Reach's current ownership boundaries
- can plausibly be reviewed and implemented without broadening the product into orchestration policy

## Proposal Sources That Are In Scope

- repeated maintainer pain during large or messy research runs
- friction around evidence ledgers, diagnostics, schemas, install, packaging, and thin collection ergonomics
- places where external users repeatedly misunderstand existing capabilities because the contract is too implicit
- thin metadata additions that help downstream tools decide for themselves

## Proposal Shapes To Prefer

- explicit opt-in flags
- ledger or schema ergonomics
- contract clarity
- neutral diagnostics
- packaging or maintainer workflow improvements
- bounded input handling improvements
- small extensions to an existing command or surface

## Proposal Shapes To Avoid

- automatic fan-out or auto-read flows
- hidden retries, hidden backoff, or hidden fallback behavior that changes caller policy
- normalized impact, trust, importance, or ranking scores
- automatic source selection or route selection
- fake channel uniformity that papers over real backend differences
- broad workflow ownership such as planning, ranking, summarization, or publishing

## Split Rule

If a raw suggestion contains both:

- a useful thin primitive
- and a policy or automation layer

propose only the thin primitive and explicitly reject or defer the rest.

## Proposal Count

Default to 3-5 proposals.

Return fewer when the evidence only supports a few strong ideas.

## Suggested Decision Guidance

- `adopt_now`
  The proposal is thin, explicit, local, and clearly valuable.
- `defer`
  The idea may help, but the boundary is not yet sharp enough or the change is too cross-cutting.
- `reject`
  The idea conflicts with caller control, duplicates existing surfaces, or adds hidden policy.

