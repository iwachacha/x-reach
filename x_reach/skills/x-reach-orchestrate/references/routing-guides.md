# Routing Guides

Choose routing hints that match the task. Do not hard-code unavailable channels; check the live contract first and then start collection in-session.

## Latest-Info Research

- Prefer official announcements, official docs, release notes, and recent primary-source pages outside X Reach.
- Use `twitter` when the request explicitly needs Twitter/X reaction, timelines, or post-level evidence.
- Use `posts` / `user_posts` only when the caller asks for a known account timeline; metric filters and `topic_fit` are explicit timeline filters, not hidden search fallback.
- Require concrete dates in the final answer.
- If the channel supports date bounds such as `since` or `until`, choose them from the live contract instead of assuming they exist.

## Community Reaction Collection

- Use `twitter` when the request is about public reaction and the configured runtime supports it.
- Pair reaction collection with the relevant official announcement or product page so community discussion has an anchor.
- Ask for `doctor --json --probe` only if Twitter/X readiness is operationally important and uncertain.

## Broad Research

- Only describe evidence-ledger fan-out when the user explicitly opts into broad or provenance-heavy research.
- Start with 2-4 small discovery queries.
- Set an explicit artifact budget before running those queries.
- Prefer a mission spec when coverage topics, topic spread, or resumable artifact layers matter.
- Prefer `--raw-mode minimal|none` and `--item-text-mode snippet|none` for discovery artifacts.
- Prefer `--save-dir .x-reach/shards` when the run needs multiple collection commands.
- Merge shards before `ledger summarize`, `ledger query`, or `plan candidates`.
- Use `plan candidates --by post --max-per-author 2 --prefer-originals --drop-noise --json` for X post review, add `--sort-by quality_score` only when utility-sorted review helps, add `--topic-fit PATH.json` only with caller-declared fit rules, and inspect `quality_reasons` / `topic_fit` rather than treating engagement as quality.
- Keep the deep-read budget small, and summarize shortlisted sources only when the deliverable calls for synthesis.

