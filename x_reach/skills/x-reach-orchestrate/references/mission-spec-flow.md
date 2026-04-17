# Mission Spec Flow

Use this reference only when the ask is broad, resumable, provenance-heavy, coverage-sensitive, or explicitly asks for a mission artifact. Keep narrow asks on `collect --json`.

## When To Prefer `collect --spec`

- multiple discovery queries or languages
- reproducible artifact layers are needed: `raw.jsonl`, `canonical.jsonl`, `ranked.jsonl`, `summary.md`, `mission-result.json`
- caller-declared coverage topics, topic spread, or bounded gap-fill matter
- the run needs resume behavior, compact retention, or judge fallback records
- downstream review will inspect candidate utility signals before deeper reads

## Spec Construction

- Set `objective`, `queries`, `target_posts`, `quality_profile`, retention, exclude rules, diversity, coverage, judge, and outputs explicitly.
- Keep discovery compact by default: `raw_mode=none|minimal`, `item_text_mode=snippet`, and a small `item_text_max_chars` unless the caller needs audit-grade payloads.
- Use `quality_profile=balanced` unless the caller clearly wants high precision or broad recall.
- Use `exclude.drop_low_content_posts=true`, `drop_retweets=true`, and `drop_replies=true` unless the caller is explicitly studying those shapes.
- Use `diversity.max_posts_per_author` and `max_posts_per_thread` for broad reaction collection so one account or thread does not dominate.
- Use `diversity.require_topic_spread=true` only with caller-declared coverage topics.
- For concurrent broad runs, include `pacing.query_delay_seconds` or pass `--query-delay`; keep it small, inspect diagnostics, and avoid retrying into repeated 409/429/conflict errors.

## Coverage Rules

- Use caller-declared topic labels, terms, and follow-up queries. Do not invent domain defaults.
- Set `coverage.enabled=true` only when the caller wants X Reach to run bounded follow-up searches for missing explicit topics.
- When topics are only for annotation or topic spread, set `coverage.enabled=false`; `max_queries=0` is acceptable in that disabled state.
- When coverage is enabled, `max_queries` must be at least `1` and should stay small.
- Treat ranked-count target gaps as report-only. They do not justify open-ended query expansion.

## Execution And Review

1. Run `x-reach channels --json` if operation support is unclear.
2. Run `x-reach doctor --json --probe` only when live readiness would change the route.
3. Write the mission spec to a file.
4. Run `x-reach collect --spec mission.json --output-dir .x-reach/missions/<run> --dry-run --json`.
5. Inspect the dry-run query count, retention, and operation options before the write-producing run.
6. Run `x-reach collect --spec mission.json --output-dir .x-reach/missions/<run> --json`; add `--concurrency 2 --query-delay 1 --throttle-cooldown 30` when the caller explicitly wants concurrent broad collection.
7. Inspect `mission-result.json` summary fields: `ranked_candidates`, `filter_drop_counts`, `quality_reason_counts`, `topic_spread_status`, `coverage_target_gap`, `coverage_query_budget_exhausted`, `throttle_sensitive_errors`, and `throttle_guard_triggered`.
8. For a separate review shortlist, run `x-reach plan candidates --input .x-reach/missions/<run>/raw.jsonl --by post --limit 20 --max-per-author 2 --prefer-originals --drop-noise --json`; add `--sort-by quality_score` only when utility-sorted review helps.
9. Treat `quality_score`, `quality_reasons`, `sort_by`, and `summary.quality_reason_counts` as deterministic utility diagnostics, not final selection or trust.

## Handoff

- Return the output directory and the main artifact paths.
- Report partial failures, exhausted query budgets, and topic-spread status plainly.
- Do not synthesize every collected post. Summarize only when the caller asked for synthesis, and base it on shortlisted or explicitly deep-read evidence.
