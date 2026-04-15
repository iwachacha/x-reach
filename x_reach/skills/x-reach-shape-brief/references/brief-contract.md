# Brief Contract

Always return the brief in this exact order:

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

## Field Intent

- `目的`: Why the research is being run and what decision or understanding it should support.
- `対象`: The product, company, repository, document set, topic, event, community, or comparison axis being investigated.
- `期待成果物`: The expected final deliverable from the downstream research run. Default to a concise synthesis with citations unless the user asks for a table, shortlist, comparison matrix, timeline, or raw evidence set.
- `鮮度要件`: How current the answer must be. Use concrete dates when recency matters.
- `含める範囲`: What the investigation should include.
- `除外範囲`: What to avoid so the downstream prompt does not sprawl.
- `地域・言語`: Geographic scope plus search/output language expectations.
- `重視ソース`: Preferred source types or named sources.
- `禁止ソース`: Sources or source classes that should not be used.
- `証拠厳密度`: How strict the downstream run should be about primary sources, cross-checking, quoting, and uncertainty handling.
- `調査スケール`: Keep this to `light`, `standard`, or `broad`.
- `前提と仮定`: Every default, inferred constraint, or unresolved ambiguity you chose on the user's behalf.

## Minimum Quality Bar

- Fill every field.
- Keep each field actionable.
- If the user gave contradictory requirements, surface that in `前提と仮定`.
- If the brief implies a latest or time-sensitive answer, say so explicitly in `鮮度要件`.
