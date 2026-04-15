$RunId = "twitter-ledger"
$EvidencePath = ".agent-reach/evidence.jsonl"

New-Item -ItemType Directory -Force -Path ".agent-reach" | Out-Null

agent-reach collect --json --save $EvidencePath --run-id $RunId --intent discovery --query-id twitter-openai --source-role social_search --channel twitter --operation search --input "OpenAI" --limit 5
agent-reach ledger validate --input $EvidencePath --json
agent-reach ledger summarize --input $EvidencePath --json
agent-reach plan candidates --input $EvidencePath --by normalized_url --limit 20 --json
