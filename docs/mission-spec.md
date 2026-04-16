# Mission Spec Runtime

`x-reach collect --spec mission.json` is the mission-driven collection path for larger X research jobs. It turns one declarative JSON spec into a deterministic batch run, then writes raw, canonical, and curated artifacts for later inspection.

## Quick Start

```powershell
x-reach collect --spec mission.json --output-dir .x-reach/missions/my-run --dry-run --json
x-reach collect --spec mission.json --output-dir .x-reach/missions/my-run --json
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
  "diversity": {
    "max_posts_per_author": 3,
    "max_posts_per_thread": 4
  },
  "retention": {
    "raw_mode": "full",
    "item_text_mode": "full"
  },
  "outputs": ["raw.jsonl", "canonical.jsonl", "ranked.jsonl", "summary.md"]
}
```

`research_high_precision` maps to the existing `precision` profile. `balanced` and `broad_recall` are also accepted.

## Output Layers

- `raw/`: sharded ledger files from each query execution.
- `raw.jsonl`: merged collection-result ledger.
- `canonical.jsonl`: one normalized item per line with run/query provenance.
- `ranked.jsonl`: deduped, keyword-filtered, diversity-constrained candidates with `rank`, `quality_score`, and `quality_reasons`.
- `summary.md`: human-readable job counts, filter drops, and top candidates.
- `mission-result.json`: JSON-first manifest for downstream tools.
- `mission-state.json`: resumable status marker for handoff/debugging.

## Implemented In This Pass

- Mission spec normalization and validation.
- Query expansion by language and time range.
- Batch execution with checkpoint/resume support.
- Raw/canonical/curated output layers.
- Deterministic keyword filtering, post dedupe, heuristic ranking, and author/thread/url diversity constraints.
- `x-reach schema mission-spec --json`.
- SDK helpers: `XReachClient.mission_plan()` and `XReachClient.collect_spec()`.

## Still Deferred

- Coverage gap fill that issues follow-up queries after inspecting missing viewpoints.
- LLM/VLM judging.
- Stance/subtopic classification beyond current deterministic metadata and diversity caps.
