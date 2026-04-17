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
x-reach collect --operation search --input "gpt-5.4" --limit 10 --json
x-reach collect --operation user --input "openai" --json
x-reach collect --operation user_posts --input "openai" --limit 50 --json
x-reach posts "openai" --limit 20 --min-likes 10 --min-views 1000 --topic-fit topic-fit.json --json
x-reach collect --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json
x-reach collect --operation search --input "OpenAI" --from openai --has media --type photos --limit 50 --json
x-reach collect --operation search --input "OpenAI" --min-likes 100 --min-views 10000 --limit 50 --json
twitter status
```

## Notes

- `twitter status` confirms authentication, but it does not guarantee that live search still works.
- In `doctor --json`, authenticated-but-unprobed Twitter/X is a `warn` with `usability_hint=authenticated_but_unprobed`.
- Treat `meta.item_shape` as a collection-shape hint, not a ranking signal.
- Treat `user_posts` metric filters and `topic_fit` as explicit account timeline filters. They do not add search-tab behavior, hidden account expansion, or final relevance judgment.

