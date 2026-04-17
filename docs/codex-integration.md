# Codex Integration

This fork keeps the X Reach Codex integration surface, but only for Twitter/X collection.

The operational boundary follows [project-principles.md](project-principles.md): Codex or the host workflow decides the research intent, while X Reach provides deterministic collection, readiness, mission, ledger, candidate, and handoff surfaces.

## Install

```powershell
uv tool install --force git+https://github.com/iwachacha/x-reach.git
x-reach skill --install
```

## Discovery first

```powershell
x-reach channels --json
x-reach doctor --json
x-reach doctor --json --probe
x-reach collect --operation search --input "OpenAI" --limit 3 --json
x-reach export-integration --client codex --format json --profile runtime-minimal
```

## Supported channel

- `twitter`

## Policy

- Use these bundled skills only when the user explicitly asks for X Reach or names one of them.
- Use native browsing/search instead of X Reach for ordinary lightweight web lookups.
- X Reach does not choose final scope, synthesis, publishing, or final selection.
- X Reach is topic-agnostic. Use caller-declared objectives, queries, coverage topics, judge intent, and exclude rules instead of assuming one domain's noise rules apply globally.
- When query tokens are too weak, use caller-declared mission `topic_fit` rules or `plan candidates --topic-fit topic-fit.json` for deterministic fit diagnostics. Do not treat those diagnostics as final truth or importance.
- Collection-only or raw-evidence handoff is a valid endpoint; do not synthesize unless the user asked for it.
- Use `collect --json` for narrow requests and `collect --spec` for broad, resumable, artifact-heavy runs.
- When a broad run uses `--concurrency > 1`, include explicit pacing such as `--query-delay 1 --throttle-cooldown 30` and inspect throttle-sensitive diagnostics before continuing.
- Inspect `operation_contracts` before choosing `since` or `until`.
- Treat `batch` and `scout` as explicit opt-in helpers, not the default path.
- Treat `agent_reach` as a compatibility shim only; new Python usage should import `x_reach`.

See [compatibility-shim.md](compatibility-shim.md) for the shim retention and removal criteria.

