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
- prefer `agent-reach collect --json --save-dir .agent-reach/shards`
- include `agent-reach ledger merge --input .agent-reach/shards --output .agent-reach/evidence.jsonl --json`
- include `agent-reach ledger summarize --input .agent-reach/evidence.jsonl --json`
- include `agent-reach plan candidates --input .agent-reach/evidence.jsonl --by normalized_url --limit 20 --json`
