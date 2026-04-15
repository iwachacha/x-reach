# Defaults And Missing-Info Policy

## Ask Only When It Changes The Outcome

Ask a follow-up only if the answer would materially change one of these:

- which sources should be prioritized or excluded
- whether the answer must be current as of the run date
- whether the investigation is local or global
- whether the final deliverable should be a synthesis, table, shortlist, timeline, or raw evidence pack

If the answer does not materially change the research route, choose a default and write it into `前提と仮定`.

## Recommended Defaults

- `期待成果物`: concise synthesis with source links for answer-first asks; shortlist or raw evidence pack with stable source links for collection-first asks
- `鮮度要件`: use latest available information at execution time for unstable topics; otherwise prefer authoritative baseline material without forcing recency
- `含める範囲`: official sources first, then high-signal secondary or community sources that directly help answer the request
- `除外範囲`: duplicate mirrors, low-signal reposts, unsupported speculation, and irrelevant side topics
- `地域・言語`: keep the user's language for output; use both Japanese and English discovery queries for globally relevant topics unless the user constrained the geography
- `重視ソース`: official docs, vendor or maintainer announcements, repositories, release notes, standards bodies, regulator sources, and direct primary discussions when available
- `禁止ソース`: content farms, unverifiable reposts, AI-generated mirrors, and citation-free summaries when better sources are available
- `証拠厳密度`: standard primary-source preference with explicit source attribution and uncertainty notes
- `調査スケール`: `standard`; use `light` for narrow verification and `broad` only when the user explicitly asks for wide coverage or provenance-heavy collection

## Latest-Info Heuristic

Treat these as recency-sensitive by default:

- company, product, model, pricing, policy, legal, benchmark, market, launch, security, and news topics
- requests containing words such as `latest`, `recent`, `today`, `now`, `最新`, `直近`, `今日`, `現在`, `今`

When this applies, encode the requirement as: execution-time latest information with concrete dates in the final answer.

## Example Assumption Style

Good:

```markdown
- 前提と仮定: 比較軸の指定がなかったため、期待成果物は「主要な違い・共通点・注意点を短くまとめた要約」に設定した。対象がグローバルなため、調査は日英併用で進める。
```

Bad:

```markdown
- 前提と仮定: いろいろ補った。
```
