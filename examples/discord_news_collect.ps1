$RunId = "twitter-discord"
$EvidencePath = ".x-reach/evidence.jsonl"
$OutputDir = ".x-reach"
$Query = "OpenAI"
$Limit = 5

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

x-reach collect --json --save $EvidencePath --run-id $RunId --intent news_discovery --query-id twitter-query --source-role social_search --channel twitter --operation search --input $Query --limit $Limit | Out-File -Encoding utf8 (Join-Path $OutputDir "twitter.json")
x-reach ledger summarize --input $EvidencePath --json | Out-File -Encoding utf8 (Join-Path $OutputDir "summary.json")
x-reach plan candidates --input $EvidencePath --by normalized_url --limit 20 --json | Out-File -Encoding utf8 (Join-Path $OutputDir "candidates.json")

