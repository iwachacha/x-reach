# Downstream Usage

X Reach is meant to be consumed as a CLI or Python dependency from another project, not copied into that project.

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
x-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json
x-reach collect --channel twitter --operation user --input "openai" --json
```

Use the exact stable channel name from `x-reach channels --json`: `twitter`.

## Evidence ledger flow

```powershell
x-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json --save .x-reach/evidence.jsonl --run-id twitter-openai --intent discovery --query-id twitter-openai --source-role social_search
x-reach ledger validate --input .x-reach/evidence.jsonl --json
x-reach ledger summarize --input .x-reach/evidence.jsonl --json
x-reach plan candidates --input .x-reach/evidence.jsonl --by normalized_url --limit 20 --json
```

## Caller control

- The caller chooses scope.
- X Reach does not choose routes, ranking, summarization, or posting.
- Keep narrow asks narrow and avoid auto-escalate behavior.
- Large-scale collection is explicit opt-in.
- `plan candidates` keeps the default `--limit 20` unless the caller asks for more.

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


