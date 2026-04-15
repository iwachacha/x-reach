# Social Collection

Use the `twitter` channel for Twitter/X collection through `twitter-cli`.

## Install and auth

```powershell
x-reach install --channels=twitter
x-reach configure twitter-cookies "auth_token=...; ct0=..."
x-reach doctor --json --probe
```

## Collection examples

```powershell
x-reach collect --channel twitter --operation search --input "gpt-5.4" --limit 10 --json
x-reach collect --channel twitter --operation user --input "openai" --json
x-reach collect --channel twitter --operation user_posts --input "openai" --limit 50 --json
x-reach collect --channel twitter --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
x-reach collect --channel twitter --operation search --input "from:openai has:media type:photos" --limit 50 --json
twitter status
```

## Notes

- `twitter status` confirms authentication, but it does not guarantee that live search still works.
- In `doctor --json`, authenticated-but-unprobed Twitter/X is a `warn` with `usability_hint=authenticated_but_unprobed`.
- Treat `extras.engagement_complete` and `extras.media_complete` as completeness hints, not ranking signals.

