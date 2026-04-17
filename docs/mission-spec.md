# Mission Spec Runtime

`x-reach collect --spec mission.json` is the mission-driven collection path for larger X research jobs. It turns one declarative JSON spec into a deterministic batch run, then writes raw, canonical, and curated artifacts for later inspection.

Mission specs are the broad-run interface described in [project-principles.md](project-principles.md). They fix caller intent, budgets, filters, coverage expectations, and outputs before collection starts so agents do not have to improvise shell orchestration mid-run.

For narrow probes, readiness checks, or one-off reads, prefer `x-reach collect --json`. Reach for mission specs when the run needs multiple queries, resumability, artifact layers, candidate planning, coverage diagnostics, or explicit judge handoff.

## Quick Start

```powershell
x-reach collect --spec mission.json --output-dir .x-reach/missions/my-run --dry-run --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/my-run --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/my-run --concurrency 2 --query-delay 1 --throttle-cooldown 30 --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/my-run --resume --json
```

## Minimal Spec

```json
{
  "objective": "Find practical complaints and requests about Feature X",
  "queries": ["Feature X bug", "\"Feature X\" lang:ja"],
  "time_range": {"since": "2026-03-01", "until": "2026-04-15"},
  "languages": ["ja"],
  "target_posts": 200,
  "quality_profile": "research_high_precision",
  "exclude": {
    "keywords": ["giveaway", "lottery"],
    "drop_retweets": true,
    "drop_replies": true,
    "drop_low_content_posts": true,
    "max_same_author_posts": 3
  },
  "topic_fit": {
    "required_any_terms": ["Feature X"],
    "required_all_terms": ["feedback"],
    "preferred_terms": ["bug", "pricing", "workflow"],
    "excluded_terms": ["giveaway", "airdrop"],
    "exact_phrases": ["Feature X"],
    "negative_phrases": ["not about Feature X"],
    "synonym_groups": [
      ["bug", "regression", "broken"],
      ["workflow", "process"]
    ]
  },
  "diversity": {
    "max_posts_per_author": 3,
    "max_posts_per_thread": 4,
    "require_topic_spread": true
  },
  "coverage": {
    "enabled": true,
    "max_queries": 4,
    "probe_limit": 25,
    "topics": [
      {
        "label": "pricing complaints",
        "terms": ["price", "pricing", "too expensive"],
        "queries": ["\"Feature X\" pricing complaint"],
        "min_posts": 3
      }
    ]
  },
  "judge": {
    "enabled": false,
    "mode": "llm",
    "candidate_limit": 20,
    "intent": "mission-relevant evidence, not off-topic chatter or promotion",
    "criteria": [
      "The post matches the mission objective",
      "The post contains concrete evidence or a first-hand claim"
    ],
    "fallback_policy": "keep_ranked"
  },
  "pacing": {
    "query_delay_seconds": 1,
    "query_jitter_seconds": 0,
    "throttle_cooldown_seconds": 30,
    "throttle_error_limit": 3
  },
  "retention": {
    "raw_mode": "full",
    "item_text_mode": "full"
  },
  "outputs": ["raw.jsonl", "canonical.jsonl", "ranked.jsonl", "summary.md"]
}
```

`research_high_precision` maps to the existing `precision` profile. `balanced` and `broad_recall` are also accepted.

## Query Operations

Mission queries default to `operation=search`. A query object may explicitly set `operation=user_posts` when the caller wants posts from a known account timeline rather than search results:

```json
{
  "queries": [
    {
      "operation": "user_posts",
      "input": "openai",
      "limit": 20,
      "originals_only": true,
      "min_likes": 10,
      "min_views": 1000
    }
  ],
  "topic_fit": {
    "required_any_terms": ["codex"]
  }
}
```

For `user_posts`, X Reach applies metric filters and active mission `topic_fit` rules client-side after timeline lookup. It does not apply search-only options such as `search_type`, `lang`, `since`, `until`, `has`, or `exclude`, and it does not add hidden author expansion.

## Output Layers

- `raw/`: sharded ledger files from each query execution.
- `raw.jsonl`: merged collection-result ledger.
- `canonical.jsonl`: one normalized item per line with run/query provenance.
- `ranked.jsonl`: deduped, topic/keyword-filtered, diversity-constrained candidates with `rank`, `quality_score`, `quality_reasons`, optional `topic_fit` diagnostics, and matched `coverage_topics` when coverage topics are configured.
- `judge.jsonl`: opt-in judge records for the top ranked candidates. The current runtime does not call a model; when `judge.enabled=true`, it writes `unjudged` fallback records so downstream tooling can test the contract without changing `ranked.jsonl`.
- `summary.md`: human-readable job counts, filter drops, and top candidates.
- `mission-result.json`: JSON-first manifest for downstream tools, including additive `summary.quality_reason_counts`, `summary.topic_spread_status`, and `diagnostics` blocks.
- `mission-state.json`: resumable status marker for handoff/debugging.

## Mission Diagnostics

Mission results include neutral diagnostics so callers can inspect the run without treating X Reach as a final analyst:

- `diagnostics.query_yield`: one row per executed query with query id, input, operation, source role, status, counts, URL count, and error code.
- `diagnostics.pacing`: normalized pacing controls plus wait counts, total wait seconds, throttle-sensitive error count, and whether the throttle guard skipped unstarted queries.
- `diagnostics.query_yield[*]`: also includes query start/finish timestamps, duration, planned/applied wait seconds, error category, retryability, and throttle-sensitive status when available.
- `diagnostics.curation.quality_reason_counts`: aggregate counts for ranked-candidate `quality_reasons`, including deterministic scoring facets such as query match, concrete detail, capped engagement, post shape, media, and URL support.
- `diagnostics.curation.topic_fit`: normalized caller-declared topic-fit rules, evaluated/matched/dropped counts, match/drop reason counts, and missing required counts when `topic_fit` is configured.
- `diagnostics.curation.topic_spread`: whether `diversity.require_topic_spread` was requested, applied, already satisfied, or skipped, plus selected topic ids, promoted count, and whether final order changed.
- `diagnostics.curation.concentration`: author, thread, and URL concentration summaries for the final ranked set.
- `diagnostics.curation.time_spread`: earliest/latest timestamps and date bucket counts when ranked candidates have timestamps.
- `coverage.diagnostics`: gap-fill budget state, used and remaining query counts, whether query budget was exhausted, and whether ranked-count target gaps are report-only.

`summary.md` mirrors the most important diagnostics with `Quality Reasons`, `Topic Fit`, and `Topic Spread` sections. These sections are meant for audit and handoff, not synthesis.

## Topic Fit

`topic_fit` is an optional caller-declared rule block for deterministic mission filtering and candidate diagnostics. It exists to replace brittle query-token fallback when the caller can state what counts as in-scope. X Reach does not ship domain-specific defaults and does not infer final truth, importance, stance, or relevance beyond the supplied strings.

Supported fields:

- `required_any_terms`: at least one term, or one of its declared synonyms, must match.
- `required_all_terms`: every term, or one of each term's declared synonyms, must match.
- `preferred_terms`: optional positive signals for scoring and reasons.
- `excluded_terms`: matching terms drop the candidate with a topic-fit drop reason.
- `exact_phrases`: optional positive phrase signals.
- `negative_phrases`: matching phrases drop the candidate with a topic-fit drop reason.
- `synonym_groups`: caller-declared groups such as `["codex", "coding agent"]`; if a group contains a required or preferred term, any term in that group can satisfy it.

Matching is deterministic, case-insensitive, Unicode-normalized substring matching. It intentionally avoids English-only word-boundary assumptions, so Japanese phrases and mixed Japanese/English text work without a tokenizer. When active `topic_fit` rules are present, mission curation uses them before the older `require_query_match` fallback; when no topic-fit rules are configured, existing query-token fallback behavior is preserved.

## Pacing And Throttle Guard

Mission specs can declare explicit pacing for broad runs:

- `query_delay_seconds`: minimum spacing between query starts. Defaults to `0`.
- `query_jitter_seconds`: bounded random extra wait before each query start. Defaults to `0`.
- `throttle_cooldown_seconds`: wait applied after a throttle-sensitive error such as HTTP 429, HTTP 409, `conflict`, or `too many requests`. Defaults to `30`.
- `throttle_error_limit`: after this many throttle-sensitive errors, unstarted queries are skipped with `reason=throttle_guard`. Defaults to `3`; set `0` to disable the stop guard.

These controls do not retry failed queries and do not change the requested scope. They only pace future query starts and record what happened in diagnostics. For large runs with `--concurrency > 1`, prefer an explicit delay such as `--query-delay 1` or a matching spec `pacing.query_delay_seconds`.

## Coverage Gap Fill

Coverage gap fill is deterministic and opt-in. When `coverage.enabled` is true, x-reach inspects `ranked.jsonl` after the first batch. If a required topic has fewer than `min_posts`, it runs at most `coverage.max_queries` additional search queries and rebuilds the raw/canonical/ranked outputs.

When `coverage.enabled=false`, `coverage.max_queries` may be omitted or set to `0` to make the no-gap-fill budget explicit. When coverage is enabled, `max_queries` must be at least `1`.

Each topic can provide:

- `label`: human-readable topic name.
- `terms`: strings used to detect whether ranked posts cover the topic.
- `queries`: explicit follow-up queries to run when the topic is missing.
- `min_posts`: minimum ranked posts expected for that topic.

If `queries` is omitted, x-reach builds a conservative query from `objective + label`. LLM judging is still deferred; this pass only fills gaps that are visible from deterministic topic terms.

Ranked candidates that match topic terms include `coverage_topics`, so downstream review can quickly see which required viewpoints each post covers.

`min_ranked_posts` and `target_gap` are diagnostics only. They show that the run is short of the requested ranked count, but they do not generate follow-up queries by themselves. x-reach only fills gaps for explicit `topics` that can produce a new, non-duplicate query.

Coverage reports include both topic gap and budget diagnostics. `topic_gap_count` is the number of declared topics below their requested minimum, while `queryable_topic_gap_count` is the subset that can still produce a follow-up query within the current query budget. When `coverage.max_queries` is exhausted and topic gaps remain, `coverage.diagnostics.query_budget_exhausted` is true.

## Topic Spread

`diversity.require_topic_spread=true` uses caller-declared `coverage.topics` as topic buckets. X Reach annotates candidates with matching `coverage_topics` before final truncation, then promotes or preserves available topic buckets in the final ranked set.

Topic spread is deterministic and bounded:

- it never invents topics;
- it only uses terms supplied in `coverage.topics`;
- it can reorder the final ranked set only to represent available declared topic buckets;
- it reports `skipped_no_topics`, `skipped_no_matches`, `already_satisfied`, `applied`, or `applied_partial` in mission diagnostics.

Topic spread is separate from coverage gap fill. If `coverage.enabled=false`, topic spread can still use declared topics that are already present in collected candidates, but it will not run additional gap-fill queries.

## Judge Contract

The `judge` block is a schema-first placeholder for future LLM/VLM or external judging after deterministic narrowing. It is explicit opt-in and bounded by `candidate_limit`.

The contract is intentionally topic-agnostic. Put the caller's current research theme in `objective`, `queries`, `coverage.topics`, and `judge.intent`; do not rely on built-in assumptions about restaurants, products, incidents, politics, software, entertainment, or any other domain.

Supported fields:

- `enabled`: when false, no judge artifact is written.
- `mode`: `llm`, `vlm`, or `external`. This records the intended judge type only.
- `provider` / `model`: optional caller-owned labels for future runners.
- `candidate_limit`: maximum ranked candidates to send to a judge.
- `intent`: the short task the judge should evaluate.
- `criteria`: string or object criteria that a future judge must answer against.
- `labels`: optional evidence categories. Defaults to `primary_evidence`, `secondary_evidence`, `chatter`, `promotion`, and `off_topic`.
- `fallback_policy`: currently `keep_ranked` or `mark_unjudged`.

No LLM/VLM call is made by this release. If `judge.enabled=true`, x-reach writes `judge.jsonl` records with `status=unjudged`, `decision=fallback_keep` for `keep_ranked`, and `fallback.reason=judge_runner_not_configured`. This lets downstream code adopt the `x-reach schema judge-result --json` contract while deterministic `ranked.jsonl` remains the source of truth.

## Implemented In This Pass

- Mission spec normalization and validation.
- Query expansion by language and time range.
- Batch execution with checkpoint/resume support.
- Explicit batch/mission pacing controls with query wait diagnostics and a bounded throttle guard for 409/429/conflict-style failures.
- Raw/canonical/curated output layers.
- Deterministic keyword filtering, post dedupe, heuristic ranking, and author/thread/url diversity constraints.
- Caller-declared `topic_fit` rules for deterministic required/preferred/excluded/phrase/synonym matching, mission filtering, candidate scoring diagnostics, and `plan candidates --topic-fit`.
- Explicit `user_posts` mission query objects with client-side metric filters and mission `topic_fit` filtering.
- Evidence-utility scoring facets for query match strength, concrete detail markers, capped engagement, post shape, media, URL support, and thin-content penalties.
- Topic spread enforcement for available caller-declared coverage topics through `diversity.require_topic_spread`.
- Mission diagnostics for query yield, quality reason counts, topic spread, author/thread/url concentration, time spread, and coverage query budgets.
- Low-content quote filtering through `exclude.drop_low_content_posts`.
- Quality filter dropped samples for debugging filter thresholds.
- One-round deterministic coverage gap fill for explicit coverage topics. Ranked-count gaps remain report-only unless a missing topic can generate a follow-up query.
- `x-reach schema mission-spec --json`.
- `x-reach schema judge-result --json` plus judge fallback records for opt-in mission specs.
- SDK helpers: `XReachClient.mission_plan()` and `XReachClient.collect_spec()`.

## Still Deferred

- Actual LLM/VLM judging after deterministic narrowing.
- Multi-round active refinement and semantic topic detection.
- Stance/subtopic classification beyond current deterministic metadata and diversity caps.
