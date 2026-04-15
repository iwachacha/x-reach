# Social Collection

Use the `twitter` channel for Twitter/X collection through `twitter-cli`.

## Install and auth

```powershell
agent-reach install --channels=twitter
agent-reach configure twitter-cookies "auth_token=...; ct0=..."
agent-reach doctor --json --probe
```

## Collection examples

```powershell
agent-reach collect --channel twitter --operation search --input "gpt-5.4" --limit 10 --json
agent-reach collect --channel twitter --operation user --input "openai" --json
agent-reach collect --channel twitter --operation user_posts --input "openai" --limit 50 --json
agent-reach collect --channel twitter --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
agent-reach collect --channel twitter --operation search --input "from:openai has:media type:photos" --limit 50 --json
twitter status
```

## Notes

- `twitter status` confirms authentication, but it does not guarantee that live search still works.
- In `doctor --json`, authenticated-but-unprobed Twitter/X is a `warn` with `usability_hint=authenticated_but_unprobed`.
- Treat `extras.engagement_complete` and `extras.media_complete` as completeness hints, not ranking signals.
