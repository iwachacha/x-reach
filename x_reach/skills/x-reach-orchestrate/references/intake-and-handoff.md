# Intake And Handoff

## If The User Already Gave A Brief

Treat it as executable when it already covers these fields:

- goal
- target
- deliverable
- freshness
- include scope
- exclude scope
- region or language
- preferred sources
- disallowed sources
- evidence strictness
- research scale
- assumptions

Normalize wording, but do not silently change intent.

## If The User Gave A Rough Ask

Create a compact internal brief first.

- Ask a follow-up only if freshness, source policy, geography, or deliverable shape would materially change.
- Otherwise choose safe defaults and record them as assumptions.
- If the user asks to gather posts or evidence rather than interpret them, set the deliverable to a shortlist or raw evidence handoff instead of a prose synthesis.
- If delegation is available and the ambiguity is outcome-changing, one intake-only subagent may shape the brief.
- If the ask is already narrow and executable, do not use a subagent.

Use this exact internal field order when you need to shape the ask before execution:

```markdown
調査ブリーフ
- 目的:
- 対象:
- 期待成果物:
- 鮮度要件:
- 含める範囲:
- 除外範囲:
- 地域・言語:
- 重視ソース:
- 禁止ソース:
- 証拠厳密度:
- 調査スケール:
- 前提と仮定:
```

## Brief Handoff Rule

Once the brief is good enough, stop reshaping and start execution.

- Do not open a second design phase.
- Do not build an external prompt.
- Move directly to `channels --json`, `doctor --json` when needed, and collection start.
