# Examples

## Example 1: Narrow Latest-Info Ask

User ask:

```text
Check the latest OpenAI posts on Twitter/X.
```

Good behavior:

- do not use a subagent
- inspect live contracts only as needed
- run a narrow collection path
- report concrete dates in the final answer

## Example 2: Ambiguous Comparison Ask

User ask:

```text
Compare the recent Twitter/X reaction to two releases.
```

Good behavior:

- decide whether missing comparison scope changes the route
- if delegation is available and helpful, use one intake-only subagent to shape the brief
- integrate that brief immediately
- keep execution on the main agent

## Example 3: Broad Research With Provenance

User ask:

```text
Research this broadly on Twitter/X and keep an evidence trail I can review later.
```

Good behavior:

- explicitly mark this as a broad run
- include compact discovery settings such as `--raw-mode none|minimal` and `--item-text-mode snippet|none`
- prefer `x-reach collect --spec` when a single mission can own queries, filters, diversity, coverage, and outputs
- otherwise use `x-reach collect --json --save-dir .x-reach/shards`
- include `x-reach ledger merge --input .x-reach/shards --output .x-reach/evidence.jsonl --json`
- include `x-reach ledger summarize --input .x-reach/evidence.jsonl --json`
- include `x-reach plan candidates --input .x-reach/evidence.jsonl --by post --limit 20 --max-per-author 2 --prefer-originals --drop-noise --json`; add `--sort-by quality_score` only when utility-sorted review is useful
- review `quality_score`, `quality_reasons`, and reason counts as shortlist diagnostics, not final judgment

