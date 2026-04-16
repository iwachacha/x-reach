# Defaults And Budget Policy

## Ask Only When It Changes Cost Or Route

Ask a follow-up only if the answer would materially change one of these:

- whether raw payloads must be preserved for audit or debugging
- whether evidence should be saved as one ledger or per-command shards
- whether the candidate shortlist must be unusually wide
- whether the final deliverable needs a table, timeline, shortlist, or raw evidence pack instead of a concise synthesis

If the answer does not materially change the execution budget, choose a safe default and record it in `前提と仮定`.

## Recommended Defaults

- `実行モード`: use `narrow` for one clear lookup, `bounded_multi_source` for small comparisons, and `broad_mission` only when the user explicitly asks for wide coverage, resumability, coverage diagnostics, or provenance-heavy work
- `発見フェーズ`: start with 2-4 discovery queries at `--limit 5` to `--limit 10`; keep channel count small and task-driven
- `成果物サイズ予算`: for discovery handoffs, prefer `--raw-mode none` or `--raw-mode minimal`, `--item-text-mode snippet`, and `--item-text-max-chars 240` unless the user explicitly needs larger retained payloads
- `証拠の残し方`: prefer `x-reach collect --spec` outputs for `broad_mission`; use `--save-dir .x-reach/shards` for manual multi-command broad runs, then merge before `ledger summarize`, `ledger query`, or `plan candidates`; use `--save .x-reach/evidence.jsonl` for a simpler single-ledger path
- `候補選別ゲート`: use `x-reach plan candidates --by post --limit 20 --max-per-author 2 --prefer-originals --drop-noise --json` before deep reads unless the user explicitly wants a wider shortlist; inspect `quality_score`, `quality_reasons`, and `summary.quality_reason_counts` as utility diagnostics, not final judgment
- `深掘り予算`: default to at most 5 selected deep reads in one round
- `最終まとめ境界`: summarize shortlisted or explicitly deep-read sources only; do not summarize every collected item
- `停止条件`: stop after the first discovery round if the candidate set is already sufficient; otherwise allow at most one follow-up round before surfacing uncertainty or asking whether to widen the run

## Broad Research Guardrail

For `broad_mission` plans:

- do not jump straight from discovery to summarizing everything collected
- declare objective, queries, retention, filters, diversity, coverage, and outputs in a mission spec before collection starts
- use `coverage.enabled=true` only when the caller wants bounded topic gap-fill queries; when topics are only for annotation or topic spread, keep `coverage.enabled=false` and use `max_queries=0` if an explicit no-gap-fill budget helps
- keep discovery artifacts compact first
- shrink with candidate planning before deep reads
- deep-read only the shortlisted sources that are actually needed for the deliverable
- keep `batch` and `scout` explicit opt-in helpers, not mandatory steps

## Example Assumption Style

Good:

```markdown
- 前提と仮定: 広めの比較だが全件監査は求められていないため、発見フェーズは 3 クエリ、成果物サイズ予算は `raw_mode=none` と `item_text_mode=snippet` を既定にした。深掘りは候補選別後の 5 件までに制限する。
```

Bad:

```markdown
- 前提と仮定: いい感じに調整した。
```

