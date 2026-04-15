# Research Execution Plan Contract

Always return the plan in this exact order:

```markdown
調査実行プラン
- 目的:
- 対象:
- 鮮度要件:
- 実行モード:
- 発見フェーズ:
- 成果物サイズ予算:
- 証拠の残し方:
- 候補選別ゲート:
- 深掘り予算:
- 最終まとめ境界:
- 停止条件:
- 前提と仮定:
```

## Field Intent

- `目的`: Why the research is being run and what downstream decision or understanding it should support.
- `対象`: The product, company, repository, document set, topic, event, community, or comparison axis being investigated.
- `鮮度要件`: How current the answer must be. Use concrete dates when recency matters.
- `実行モード`: Keep this to `narrow`, `bounded_multi_source`, or `broad_with_ledger`.
- `発見フェーズ`: The initial discovery shape, including channels, number of discovery queries, and per-query limits.
- `成果物サイズ予算`: The artifact-retention policy for discovery outputs, including `raw_mode`, `item_text_mode`, and snippet size expectations.
- `証拠の残し方`: Whether to use `--save` or `--save-dir`, plus merge, summarize, validate, or query steps when they are needed.
- `候補選別ゲート`: How the run shrinks collected items before deep reads, including whether `plan candidates` is used and the candidate limit.
- `深掘り予算`: The maximum number of URLs, posts, repos, or documents to deep-read in one round.
- `最終まとめ境界`: What the final synthesis may summarize and what it must leave out to avoid summarizing every collected item.
- `停止条件`: When to stop discovery or defer more collection.
- `前提と仮定`: Every default, inferred constraint, or unresolved ambiguity you chose on the user's behalf.

## Minimum Quality Bar

- Fill every field.
- Keep each field actionable enough to drive real Agent Reach commands.
- If the plan is broad, make the artifact budget and stop conditions explicit.
- If the plan implies latest or time-sensitive answers, say so explicitly in `鮮度要件`.
