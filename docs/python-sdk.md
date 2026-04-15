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

## Choosing CLI vs SDK

- Use `x-reach collect --json` when the host project can shell out and wants the most portable integration surface.
- Use `XReachClient` when the host project already manages a Python environment and can install X Reach into it.


