# X Reach Python SDK

`XReachClient` is the primary SDK surface, and this fork only exposes the `twitter` namespace.

## Install

CLI-only installs:

```powershell
uv tool install .
```

SDK installs for a caller-managed Python environment:

```powershell
uv pip install -e .
```

Or install the current fork directly:

```powershell
uv pip install "x-reach @ git+https://github.com/iwachacha/x-reach.git"
```

## Basic usage

```python
from x_reach import XReachClient

client = XReachClient()

twitter_posts = client.twitter.user_posts("openai", limit=5)
original_posts = client.twitter.user_posts("openai", limit=5, originals_only=True)
hashtag_posts = client.twitter.hashtag("OpenAI", limit=5)
windowed_search = client.collect(
    "twitter",
    "search",
    "OpenAI",
    limit=5,
    since="2026-01-01",
    until="2026-12-31",
)
quality_search = client.twitter.search(
    "OpenAI",
    min_likes=100,
    min_views=10000,
    has=["links"],
)
ledger_summary = client.ledger_summarize(".x-reach/evidence.jsonl")
ledger_validation = client.ledger_validate(
    ".x-reach/evidence.jsonl",
    require_metadata=True,
)
candidates = client.plan_candidates(
    ".x-reach/evidence.jsonl",
    by="post",
    max_per_author=2,
    prefer_originals=True,
    drop_noise=True,
    min_seen_in=2,
)
matches = client.ledger_query(
    ".x-reach/evidence.jsonl",
    filters=["channel == twitter", "operation == search"],
    limit=5,
    fields=["channel", "operation", "result.meta.input"],
)
```

If your host project only needs a machine-readable subprocess interface, prefer `x-reach collect --json`.

## Result shape

Every collection call returns the same envelope:

- `ok`
- `channel`
- `operation`
- `items`
- `raw`
- `meta`
- `error`

Use `items` for downstream automation and `raw` when you need backend-native details.

## Ledger and candidate helpers

`XReachClient` also exposes thin wrappers around the evidence-ledger utilities:

- `ledger_merge(input_path, output_path)`
- `ledger_validate(input_path, require_metadata=False, filters=None)`
- `ledger_summarize(input_path, filters=None)`
- `ledger_query(input_path, filters=None, limit=None, fields=None)`
- `plan_candidates(input_path, ..., min_seen_in=None)`

Leave `min_seen_in` unset for narrow or one-off collection. It becomes useful when a broader run spans multiple query variants and you want candidates that resurfaced across repeated sightings.

## Choosing CLI vs SDK

- Use `x-reach collect --json` when the host project can shell out and wants the most portable integration surface.
- Use `XReachClient` when the host project already manages a Python environment and can install X Reach into it.
- Use `--warn-missing-evidence-metadata` in CLI flows only when provenance completeness matters; SDK callers can decide how strict they want to be without an automatic warning.


