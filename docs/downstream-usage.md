# Downstream Usage

X Reach is meant to be consumed as a CLI or Python dependency from another project, not copied into that project.

For project-level design boundaries, see [project-principles.md](project-principles.md). In short: X Reach collects, normalizes, filters, dedupes, and hands off X evidence; the host project owns the research meaning and final deliverable.

## Install

```powershell
uv tool install --force git+https://github.com/iwachacha/x-reach.git
x-reach skill --install
```

## Core flow

```powershell
x-reach channels --json
x-reach doctor --json
x-reach doctor --json --probe
x-reach collect --operation search --input "OpenAI" --limit 5 --json
x-reach collect --operation user --input "openai" --json
x-reach posts "openai" --limit 20 --min-likes 10 --topic-fit topic-fit.json --json
```

Use the exact stable channel name from `x-reach channels --json`: `twitter`.

## Evidence ledger flow

```powershell
x-reach collect --operation search --input "OpenAI" --limit 5 --json --save .x-reach/evidence.jsonl --run-id twitter-openai --intent discovery --query-id twitter-openai --source-role social_search
x-reach ledger validate --input .x-reach/evidence.jsonl --json
x-reach ledger summarize --input .x-reach/evidence.jsonl --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by normalized_url --limit 20 --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --sort-by quality_score --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --topic-fit topic-fit.json --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by post --max-per-author 2 --prefer-originals --drop-noise --min-seen-in 2 --json
```

## Caller control

- The caller chooses scope.
- X Reach does not choose final scope, synthesis, publishing, or final selection.
- Collection-only or raw-evidence handoff is a valid final deliverable when the caller wants posts or machine-readable artifacts instead of prose synthesis.
- Keep narrow asks narrow and avoid auto-escalate behavior.
- Large-scale collection is explicit opt-in.
- Use `collect --spec` for broad, resumable, artifact-heavy X runs instead of ad hoc shell orchestration.
- For broad runs with `--concurrency > 1`, set explicit pacing such as `--query-delay 1 --throttle-cooldown 30`; 409/429/conflict-style failures remain normal errors but can slow or stop unstarted queries through the throttle guard.
- `plan candidates` keeps the default `--limit 20` unless the caller asks for more.
- `plan candidates --json` exposes deterministic `quality_score`, `quality_reasons`, and aggregate reason counts so downstream review can audit utility signals without treating them as final judgment.
- `plan candidates --sort-by quality_score` is opt-in evidence-utility ordering; default output stays first-seen for compatibility.
- `plan candidates --topic-fit topic-fit.json` applies caller-owned deterministic fit rules and returns `topic_fit` diagnostics, including compact match/drop reasons. Use it when query tokens are too weak, but keep final selection in the host workflow.
- `posts` / `collect --operation user_posts` can apply caller-owned metric filters and `topic_fit` rules to account timelines. Use this when the caller explicitly wants timeline evidence; it is still not a search-tab fallback or author deep-read expansion.
- `--min-seen-in` is useful for broad or multilingual runs where you want candidates that resurfaced across multiple queries; keep it off for narrow probes.
- Saved evidence does not warn by default; use `--warn-missing-evidence-metadata` when downstream provenance completeness matters.

## GitHub Actions

```yaml
- uses: iwachacha/x-reach/.github/actions/setup-x-reach@main
  with:
    install-twitter-cli: "true"
```

## Notes

- For ordinary lightweight searches or one-off web lookups, use Codex's built-in browsing/search instead of X Reach.
- Use `doctor --json --probe` when the caller needs operation-level readiness instead of authenticated-only Twitter/X status.
- Downstream projects do not need `.codex-plugin`, `.mcp.json`, or `x_reach/skills` files when they are using the CLI.


