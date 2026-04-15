$RunId = "twitter-ledger"
$EvidencePath = ".x-reach/evidence.jsonl"

New-Item -ItemType Directory -Force -Path ".x-reach" | Out-Null

x-reach collect --json --save $EvidencePath --run-id $RunId --intent discovery --query-id twitter-openai --source-role social_search --channel twitter --operation search --input "OpenAI" --limit 5
x-reach ledger validate --input $EvidencePath --json
x-reach ledger summarize --input $EvidencePath --json
x-reach plan candidates --input $EvidencePath --by normalized_url --limit 20 --json

