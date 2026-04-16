---
name: x-reach-budgeted-research
description: Shape broad or provenance-heavy research asks into a bounded X Reach execution plan with explicit artifact, discovery, candidate, and deep-read budgets. Use only when the user explicitly asks to use X Reach or names this skill, and the task is broad enough that token or artifact size needs to be controlled before collection begins.
---

# X Reach Budgeted Research

Use this skill only when the user explicitly asks to use X Reach or names this skill, and the task is broad, multi-source, or provenance-heavy enough that collection needs explicit budget guardrails first. For ordinary lightweight searching, use the model's native browsing/search instead.

Turn the user's research request into one bounded execution plan that downstream X Reach collection can follow without inflating artifact size or synthesis cost.

This skill sets execution budgets and phase gates. It does not start collection and it does not generate a separate external prompt string.

## Workflow

1. Read [references/plan-contract.md](references/plan-contract.md) and use that contract exactly.
2. Read [references/defaults.md](references/defaults.md) before asking any question.
3. Ask only when the answer would materially change raw retention, evidence persistence, candidate breadth, deep-read count, or final deliverable shape.
4. If the user already gave execution-budget constraints, normalize them to the fixed contract instead of reinterpreting them.
5. For broad or provenance-heavy work, choose explicit discovery, artifact, candidate, and deep-read budgets before any collection starts.
6. Keep the result concise, operational, and ready for downstream execution.

## Output Rules

- Return a single plan using the exact field order from [references/plan-contract.md](references/plan-contract.md).
- Default to Japanese unless the user explicitly asks for another language.
- Keep assumptions explicit. Never leave a field blank.
- Do not start collection here. Stop at the execution plan.

## References

- Contract and field definitions: [references/plan-contract.md](references/plan-contract.md)
- Recommended defaults and budget policy: [references/defaults.md](references/defaults.md)
- Example broad and bounded plans: [references/examples.md](references/examples.md)

