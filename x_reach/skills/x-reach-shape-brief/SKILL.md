---
name: x-reach-shape-brief
description: Shape vague research or information-gathering requests into a fixed brief for downstream X Reach execution. Use only when the user explicitly asks to use X Reach or names this skill, and you need a structured brief before any X Reach collection begins.
---

# X Reach Shape Brief

Use this skill only when the user explicitly asks to use X Reach or names this skill, and you need to stop at brief formation before collection begins. For ordinary lightweight searching, use the model's native browsing/search instead.

Convert the user's rough request into one fixed research brief that an execution or orchestration skill can consume without further interpretation.

This skill outputs a fixed brief contract for downstream X Reach use. It does not generate a separate external prompt string.
If the user also needs execution-budget decisions for a broad or provenance-heavy run, hand off to `x-reach-budgeted-research` after brief shaping instead of stretching this brief contract.

## Workflow

1. Read [references/brief-contract.md](references/brief-contract.md) and use that contract exactly.
2. Read [references/defaults.md](references/defaults.md) before asking any question.
3. Ask only when the missing information would materially change freshness handling, source selection, geography/language, or deliverable shape.
4. Fill every other missing field with the recommended defaults and record those choices under `前提と仮定`.
5. Keep the result concise, operational, and implementation-ready. Do not turn the brief into an essay.
6. If the user already gave a structured brief, normalize it to the fixed contract instead of reinterpreting the request.

## Output Rules

- Return a single brief using the exact field order from [references/brief-contract.md](references/brief-contract.md).
- Default to Japanese unless the user explicitly asks for another language.
- Keep assumptions explicit. Never leave a field blank.
- Do not generate an external prompt or start collection here. Stop at the brief.

## References

- Contract and field definitions: [references/brief-contract.md](references/brief-contract.md)
- Default values and when to ask: [references/defaults.md](references/defaults.md)
- Example rough asks and normalized briefs: [references/examples.md](references/examples.md)

