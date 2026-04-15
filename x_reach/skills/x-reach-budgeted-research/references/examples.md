# Examples

## Example 1: Broad Twitter/X Research With Evidence

- discovery phase: start with 2-3 Twitter/X searches and keep each query at `--limit 5` to `--limit 8`
- artifact sizing: use `--raw-mode none`, `--item-text-mode snippet`, and `--item-text-max-chars 240`
- persistence: prefer `--save-dir .x-reach/shards`, then merge before downstream ledger work
- candidates: use `plan candidates --by normalized_url --limit 20 --json`
- deep reads: keep the shortlist small and explicit

## Example 2: Small Comparison

- discovery phase: use 2-3 Twitter/X commands at `--limit 5`
- artifact sizing: keep discovery artifacts compact
- persistence: skip ledger writes unless provenance was explicitly requested
- deep reads: stop after a small shortlisted set

