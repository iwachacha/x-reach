---
name: x-reach-orchestrate
description: Run one-shot in-session research orchestration with X Reach. Use only when the user explicitly asks to use X Reach or names this skill, and wants the same session to move from intake to live X Reach checks and collection.
---

# X Reach Orchestrate

Use this skill only when the user explicitly asks to use X Reach or names this skill. If the user only wants a quick web lookup, use the model's native browsing/search instead of X Reach.

Take a rough or structured research ask and move it to actual X Reach collection start in the same session.

## Workflow

1. Read [references/intake-and-handoff.md](references/intake-and-handoff.md) to decide whether the ask is already executable.
2. Read [references/subagent-policy.md](references/subagent-policy.md) before spawning any subagent.
3. If intake ambiguity would materially change freshness, sources, geography, or deliverable shape, normalize the ask to the fixed brief contract first.
4. If the ask is broad, provenance-heavy, or likely to create large machine-readable handoffs, set an explicit execution budget before collection starts.
5. Use [references/orchestration-flow.md](references/orchestration-flow.md) to choose the execution path.
6. Use [references/routing-guides.md](references/routing-guides.md) for source and channel hints that match the task type.
7. Start actual X Reach checks and collection in-session. Do not stop at a prompt.

## Execution Rules

- Default to Japanese.
- Only use this skill when the user explicitly asks to use X Reach or names this skill. For ordinary lightweight web lookups, use the model's native browsing/search instead.
- Keep subagent usage conservative. Use at most one intake-only subagent per user request, and only when delegation is available and the ambiguity would materially change the research route.
- Keep `channels --json`, `doctor --json`, channel choice, collection start, and the final deliverable on the main agent.
- Keep lightweight asks lightweight. Default to `x-reach collect --json`.
- Collection-only or evidence-pack handoff is a valid endpoint. Do not force synthesis when the caller wants posts or machine-readable artifacts.
- When you name channels in commands or handoffs, use the exact stable names from `x-reach channels --json`.
- Use pagination or time-window controls only after checking live `operation_contracts`.
- For broad runs, make artifact budgets explicit before collection: prefer `--raw-mode minimal|none`, `--item-text-mode snippet|none`, candidate gating before deep reads, and a small deep-read cap.
- Use evidence ledgers, candidate planning, `batch`, or `scout` only when the user explicitly asks for broad or provenance-heavy research.
- When the request is freshness-sensitive, confirm concrete dates and use absolute dates in the final answer.

## References

- Intake decision and brief handoff: [references/intake-and-handoff.md](references/intake-and-handoff.md)
- Orchestration flow and collection-start rules: [references/orchestration-flow.md](references/orchestration-flow.md)
- Subagent decision policy: [references/subagent-policy.md](references/subagent-policy.md)
- Task-type routing guidance: [references/routing-guides.md](references/routing-guides.md)
- Example runs and edge cases: [references/examples.md](references/examples.md)

