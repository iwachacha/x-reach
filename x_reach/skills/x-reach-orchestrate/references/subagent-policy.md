# Subagent Policy

Subagents are optional accelerators, not the default path.

## When They Help

Use one intake-only subagent if all of these are true:

- delegation is available and authorized
- the request is rough enough that ambiguity would materially change the research route
- the immediate blocker is clarifying the ask, not starting collection

Typical good cases:

- multiple comparison targets with unclear success criteria
- mixed requests that combine product, community, and market angles
- vague asks where freshness, geography, or deliverable shape is still missing

## When They Are Not Worth It

Do not use a subagent when:

- the target and deliverable are already clear
- the task is a narrow verification or straightforward latest-info lookup
- the next correct step is already `channels --json`, `doctor --json`, or `collect --json`

## Hard Limits

- use at most one subagent per user request
- use it for intake only
- do not chain or recurse into more subagents
- do not delegate channel checks, collection start, or final synthesis

## Main-Agent Ownership

The main agent always owns:

- deciding whether delegation is worth it
- integrating the shaped brief
- checking live channel and readiness data
- starting collection
- synthesizing the final answer
