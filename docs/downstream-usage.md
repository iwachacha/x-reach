# Downstream Usage

Twitter Reach is meant to be consumed as a CLI or Python dependency from another project, not copied into that project.

## Install

```powershell
uv tool install --force git+https://github.com/iwachacha/twitter-reach.git
agent-reach skill --install
```

## Core flow

```powershell
agent-reach channels --json
agent-reach doctor --json
agent-reach doctor --json --probe
agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json
agent-reach collect --channel twitter --operation user --input "openai" --json
```

Use the exact stable channel name from `agent-reach channels --json`: `twitter`.

## Evidence ledger flow

```powershell
agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 5 --json --save .agent-reach/evidence.jsonl --run-id twitter-openai --intent discovery --query-id twitter-openai --source-role social_search
agent-reach ledger validate --input .agent-reach/evidence.jsonl --json
agent-reach ledger summarize --input .agent-reach/evidence.jsonl --json
agent-reach plan candidates --input .agent-reach/evidence.jsonl --by normalized_url --limit 20 --json
```

## Caller control

- The caller chooses scope.
- Agent Reach does not choose routes, ranking, summarization, or posting.
- Keep narrow asks narrow and avoid auto-escalate behavior.
- Large-scale collection is explicit opt-in.
- `plan candidates` keeps the default `--limit 20` unless the caller asks for more.

## GitHub Actions

```yaml
- uses: iwachacha/twitter-reach/.github/actions/setup-agent-reach@main
  with:
    install-twitter-cli: "true"
```

## Notes

- For ordinary lightweight searches or one-off web lookups, use Codex's built-in browsing/search instead of Agent Reach.
- Use `doctor --json --probe` when the caller needs operation-level readiness instead of authenticated-only Twitter/X status.
- Downstream projects do not need `.codex-plugin`, `.mcp.json`, or `agent_reach/skills` files when they are using the CLI.
