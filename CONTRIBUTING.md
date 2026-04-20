# Contributing to X Reach

Thank you for contributing. This fork is intentionally narrow: Windows-first, Codex-friendly, and focused on external integration surfaces that other projects can depend on.

## Local setup

```powershell
git clone https://github.com/YOUR_USERNAME/x-reach.git
cd x-reach
uv sync --extra dev
```

If you prefer editable installs:

```powershell
uv pip install -e ".[dev]"
```

## Validation commands

Run these before submitting changes:

```powershell
python -m pytest tests/test_cli_contracts.py -q
python -m pytest -q
uvx ruff check .
uvx mypy --follow-imports skip x_reach/cli agent_reach/cli.py
uvx --from build pyproject-build --wheel --sdist
```

The staged `mypy` target is intentional. Full-package typing is still blocked by pre-existing errors outside the refactored CLI boundary, so CI currently type-checks the rebuilt `x_reach.cli` surface and the legacy `agent_reach.cli` wrapper first.

If dependencies changed, refresh the lock file too:

```powershell
uv lock
```

## Project direction

Keep contributions aligned with [docs/project-principles.md](docs/project-principles.md) and the current fork goals:

- Windows-native install and diagnostics
- machine-readable registry and readiness output
- thin read-only collection via `XReachClient` and `x-reach collect --json`
- declarative broad collection via `x-reach collect --spec`
- deterministic filtering, dedupe, candidate scoring, diversity constraints, and auditable handoff artifacts
- downstream integration support for Codex and similar hosts

Avoid reintroducing:

- removed legacy channels
- shell-specific Linux or Bash-first automation
- interactive prompts inside the collection path
- docs that claim this repo owns final interpretation, synthesis, scheduling, publishing, or caller scope

When a design choice is unclear, use this order:

1. improve X collection result quality
2. keep large runs from becoming fragile
3. make agent and downstream usage stable
4. improve reproducibility and auditability
5. preserve broad topic usefulness without hard-coded domain policy
6. keep caller control explicit
7. minimize maintenance weight

## Adding or changing channels

When you change channel support, update all of the following together:

1. `x_reach/channels/` metadata and health checks
2. `x_reach/adapters/` collection implementation
3. tests for channel contract, adapter behavior, and CLI output
4. docs and skill references

## CLI Maintenance

The CLI implementation is split across:

1. `x_reach/cli/main.py`
2. `x_reach/cli/__main__.py`
3. `x_reach/cli/parser.py`
4. `x_reach/cli/commands/*.py`
5. `x_reach/cli/renderers/*.py`

When changing CLI behavior, update parser registration, the command handler, contract tests in `tests/test_cli_contracts.py`, and any affected docs in one boundary.

Every channel contract must include:

- `name`
- `description`
- `backends`
- `auth_kind`
- `entrypoint_kind`
- `operations`
- `required_commands`
- `host_patterns`
- `example_invocations`
- `supports_probe`
- `probe_operations`
- `probe_coverage`
- `install_hints`
- `operation_contracts`

## Updating the local install

```powershell
git pull --ff-only
uv tool install . --reinstall
x-reach doctor --json
```

## Pull requests

- Prefer small, focused changes
- Include tests for new behavior
- Update docs when the public surface changes
- Keep machine-readable outputs stable unless a schema change is deliberate


