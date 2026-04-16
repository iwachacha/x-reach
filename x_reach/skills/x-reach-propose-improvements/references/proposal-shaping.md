# Proposal Shaping

Use this guide when turning external research into X Reach improvement proposals.

## Goal

Produce a short list of proposals that:

- clearly address observed friction
- fit X Reach's current ownership boundaries
- preserve topic generality across arbitrary research themes and collection scales
- can plausibly be reviewed and implemented without broadening the product into orchestration policy

## Proposal Sources That Are In Scope

- repeated maintainer pain during large or messy research runs
- friction around evidence ledgers, diagnostics, schemas, install, packaging, and thin collection ergonomics
- places where external users repeatedly misunderstand existing capabilities because the contract is too implicit
- thin metadata additions that help downstream tools decide for themselves
- topic-fit failures that can be solved through generic primitives instead of one-domain defaults

## Proposal Shapes To Prefer

- explicit opt-in flags
- ledger or schema ergonomics
- contract clarity
- neutral diagnostics
- packaging or maintainer workflow improvements
- bounded input handling improvements
- small extensions to an existing command or surface
- theme-neutral controls that let callers declare objective, coverage, intent, or exclusions

## Proposal Shapes To Avoid

- automatic fan-out or auto-read flows
- hidden retries, hidden backoff, or hidden fallback behavior that changes caller policy
- normalized impact, trust, importance, or ranking scores
- automatic source selection or route selection
- fake channel uniformity that papers over real backend differences
- broad workflow ownership such as planning, ranking, summarization, or publishing
- domain-specific defaults that turn one investigation example into product policy

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

