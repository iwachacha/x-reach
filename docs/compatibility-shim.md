# Compatibility Shim

`x_reach` is the primary runtime package. `agent_reach` remains only as a compatibility shim for older imports, scripts, and bundled skill cleanup paths that still refer to the upstream Agent Reach name.

## Current Policy

- New code should import from `x_reach`.
- Docs and examples should prefer `x-reach` for the CLI and `x_reach` for Python.
- The primary CLI implementation lives under the `x_reach.cli` package; `agent_reach.cli` must remain a wrapper-only entrypoint.
- `agent_reach` modules must stay thin wrappers around `x_reach` modules. Do not add new runtime logic there.
- Compatibility aliases such as `AgentReachClient` may remain while downstream projects migrate to `XReachClient`.

## Keep The Shim While

- a focused compatibility regression test still imports `agent_reach` to prove backward compatibility while primary runtime tests import `x_reach`;
- existing release notes, uninstall paths, or skill cleanup flows need legacy names;
- there is no migration note in the README, SDK docs, and Codex integration docs;
- removing the shim would break a documented public surface.

## Deletion Criteria

The shim can be removed in a future major release only after all of these are true:

- repo tests import `x_reach` directly except for the dedicated compatibility shim regression, or no compatibility test remains;
- docs and packaged skill guidance no longer instruct users to import `agent_reach`;
- the changelog has announced at least one release window for removal;
- `uv run x-reach doctor --json --probe` and the core CLI smoke tests pass without any `agent_reach` import path;
- downstream migration guidance points users from `agent_reach.AgentReachClient` to `x_reach.XReachClient`.

## Review Checklist

Before deleting or changing the shim, run:

```powershell
rg -n "agent_reach|AgentReach" README.md docs x_reach tests agent_reach
uv run pytest tests/ -q --tb=short
uv run x-reach doctor --json --probe
```

Treat any non-wrapper logic found under `agent_reach/` as a cleanup bug: move the behavior into `x_reach/` first, then keep or remove the wrapper according to the criteria above.
