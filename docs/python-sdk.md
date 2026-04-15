# Agent Reach Python SDK

`AgentReachClient` remains available, but this fork only exposes the `twitter` namespace.

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
uv pip install "agent-reach @ git+https://github.com/iwachacha/twitter-reach.git"
```

## Basic usage

```python
from agent_reach import AgentReachClient

client = AgentReachClient()

twitter_posts = client.twitter.user_posts("openai", limit=5)
windowed_search = client.collect(
    "twitter",
    "search",
    "OpenAI",
    limit=5,
    since="2026-01-01",
    until="2026-12-31",
)
```

If your host project only needs a machine-readable subprocess interface, prefer `agent-reach collect --json`.

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

- Use `agent-reach collect --json` when the host project can shell out and wants the most portable integration surface.
- Use `AgentReachClient` when the host project already manages a Python environment and can install Agent Reach into it.
