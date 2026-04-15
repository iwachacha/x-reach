$RunId = "twitter-discord"
$EvidencePath = ".agent-reach/evidence.jsonl"
$OutputDir = ".agent-reach"
$Query = "OpenAI"
$Limit = 5

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

agent-reach collect --json --save $EvidencePath --run-id $RunId --intent news_discovery --query-id twitter-query --source-role social_search --channel twitter --operation search --input $Query --limit $Limit | Out-File -Encoding utf8 (Join-Path $OutputDir "twitter.json")
agent-reach ledger summarize --input $EvidencePath --json | Out-File -Encoding utf8 (Join-Path $OutputDir "summary.json")
agent-reach plan candidates --input $EvidencePath --by normalized_url --limit 20 --json | Out-File -Encoding utf8 (Join-Path $OutputDir "candidates.json")
