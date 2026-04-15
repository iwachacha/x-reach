---
name: agent-reach-propose-improvements
description: Generate policy-compatible improvement proposals for Agent Reach from external research, friction logs, or other AI-generated findings. Use when Codex should compress raw findings into a short shortlist before formal adopt/reject review; if the user already has a concrete proposal list and wants the decision now, use `agent-reach-maintain-proposals`.
---

# Agent Reach Propose Improvements

Turn external findings into clean candidate proposals for Agent Reach itself.

## Workflow

1. Read [references/proposal-shaping.md](references/proposal-shaping.md) before drafting proposals.
2. Compress the provided research or friction evidence into a few concrete themes first. Do not mirror every raw suggestion.
3. Draft only proposals that stay inside Agent Reach's thin-interface and caller-control policy.
4. For each proposal, include a suggested maintainer decision and the smallest safe patch boundary.
5. Hand the shortlist to [../agent-reach-maintain-proposals/SKILL.md](../agent-reach-maintain-proposals/SKILL.md) when the user wants formal adopt or reject judgment.

## Rules

- Start from observed maintainer or user friction, not from abstract product ideation.
- Prefer extending an existing surface over inventing a parallel command or workflow.
- Split a good primitive away from any hidden policy layer.
- Self-reject auto-routing, auto-ranking, hidden deep-read, impact scoring, or fake uniformity proposals.
- If the user already pasted a concrete proposal list and asked for adopt/reject/defer judgment, do not reshape it again here; hand it to `agent-reach-maintain-proposals`.
- Keep the output short. A strong shortlist is better than a long idea dump.
- Do not start implementation from this skill.

## Output

For each proposal, return:

- `proposal`
- `evidence_basis`
- `suggested_decision`: `adopt_now` | `defer` | `reject`
- `why`
- `boundary`
- `touchpoints`

## References

- Proposal shaping rules: [references/proposal-shaping.md](references/proposal-shaping.md)
- Handoff to review and shipping: [references/handoff.md](references/handoff.md)
