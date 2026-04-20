# -*- coding: utf-8 -*-
"""Tests that lock in repository cleanup decisions."""

import ast
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_legacy_files_are_removed():
    repo_root = _repo_root()

    assert not (repo_root / "policy.md").exists()
    assert not (repo_root / ".mcp.json").exists()
    assert not (repo_root / ".github" / "actions" / "setup-agent-reach").exists()
    assert not (repo_root / ".github" / "workflows" / "agent-reach-smoke.yml").exists()
    assert not (repo_root / "agent_reach" / "channels" / "github.py").exists()
    assert not (repo_root / "agent_reach" / "channels" / "web.py").exists()
    assert not (repo_root / "agent_reach" / "adapters" / "reddit.py").exists()
    assert not (repo_root / "agent_reach" / "skills").exists()
    assert not (repo_root / "agent_reach" / "source_hints.py").exists()
    assert not (repo_root / "agent_reach" / "extraction_hygiene.py").exists()
    assert not (repo_root / "agent_reach" / "utils" / "paths.py").exists()
    assert not (repo_root / "x_reach" / "skills" / "x-reach" / "references" / "search.md").exists()


def test_docs_folder_only_contains_supported_docs():
    docs_dir = _repo_root() / "docs"
    names = {path.name for path in docs_dir.iterdir()}

    expected_docs = {
        "compatibility-shim.md",
        "codex-integration.md",
        "downstream-usage.md",
        "improvement-plan.md",
        "install.md",
        "mission-spec.md",
        "project-principles.md",
        "python-sdk.md",
        "troubleshooting.md",
    }

    assert names == expected_docs


def test_llms_txt_points_at_current_fork_docs():
    llms = (_repo_root() / "llms.txt").read_text(encoding="utf-8")

    assert "github.com/iwachacha/x-reach/blob/main/docs/project-principles.md" in llms
    assert "github.com/iwachacha/x-reach/blob/main/docs/improvement-plan.md" in llms
    assert "github.com/iwachacha/x-reach/blob/main/docs/install.md" in llms
    assert "github.com/iwachacha/Agent-Reach/blob/main/" not in llms
    assert "twitter" in llms


def test_caller_control_policy_is_documented_consistently():
    repo_root = _repo_root()
    files = {
        "principles": repo_root / "docs" / "project-principles.md",
        "readme": repo_root / "README.md",
        "skill": repo_root / "x_reach" / "skills" / "x-reach" / "SKILL.md",
        "agent_prompt": repo_root / "x_reach" / "skills" / "x-reach" / "agents" / "openai.yaml",
    }

    texts = {name: path.read_text(encoding="utf-8") for name, path in files.items()}

    assert "Deterministic Before LLM" in texts["principles"]
    assert "Mission Spec First For Broad Runs" in texts["principles"]
    assert "caller owns" in texts["principles"].casefold()

    assert "X Reach does not choose" in texts["readme"]
    assert "auto-escalate" in texts["readme"]
    assert "explicit opt-in" in texts["readme"]
    assert "collect --spec" in texts["readme"]
    assert "--limit 20" in texts["readme"]

    assert "The caller chooses scale" in texts["skill"]
    assert "auto-escalate" in texts["skill"]
    assert "explicit opt-in" in texts["skill"]
    assert "deterministic processing" in texts["skill"]
    assert "--limit 20" in texts["skill"]

    assert "does not choose scope" in texts["agent_prompt"]


def test_agent_reach_python_modules_are_compatibility_shims():
    repo_root = _repo_root()
    shim_root = repo_root / "agent_reach"
    alias_modules = {
        Path("__init__.py"),
        Path("client.py"),
        Path("core.py"),
    }

    for path in shim_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(shim_root)
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text)
        runtime_defs = (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
        )
        assert not any(isinstance(node, runtime_defs) for node in ast.walk(tree)), relative

        if relative in alias_modules:
            assert "from x_reach." in text or "from x_reach " in text, relative
            assert "__all__" in text, relative
            continue

        expected_target = _expected_x_reach_wrapper_target(relative)
        assert "sys.modules[__name__] = import_module(" in text, relative
        assert expected_target in text, relative


def test_agent_reach_schema_file_mirrors_x_reach_schema_file():
    repo_root = _repo_root()

    assert (
        repo_root / "agent_reach" / "schema_files" / "collection_result.schema.json"
    ).read_text(encoding="utf-8") == (
        repo_root / "x_reach" / "schema_files" / "collection_result.schema.json"
    ).read_text(encoding="utf-8")


def test_public_guidance_keeps_x_reach_as_primary_python_surface():
    repo_root = _repo_root()
    roots = [
        repo_root / "README.md",
        repo_root / "docs",
        repo_root / "examples",
        repo_root / "x_reach" / "skills",
    ]
    texts: dict[str, str] = {}
    for root in roots:
        if root.is_file():
            texts[str(root.relative_to(repo_root))] = root.read_text(encoding="utf-8")
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".md", ".py", ".ps1", ".yaml", ".yml", ".json"}:
                continue
            texts[str(path.relative_to(repo_root))] = path.read_text(encoding="utf-8")

    combined = "\n".join(texts.values())
    assert "from x_reach import XReachClient" in combined

    offenders = [
        name
        for name, text in texts.items()
        if name != "docs/compatibility-shim.md"
        and ("from agent_reach" in text or "import agent_reach" in text)
    ]
    assert offenders == []


def test_skill_suite_files_exist():
    repo_root = _repo_root()
    suite_root = repo_root / "x_reach" / "skills"
    expected = [
        "x-reach",
        "x-reach-shape-brief",
        "x-reach-budgeted-research",
        "x-reach-orchestrate",
        "x-reach-propose-improvements",
        "x-reach-maintain-proposals",
        "x-reach-maintain-release",
    ]

    for skill_name in expected:
        skill_dir = suite_root / skill_name
        assert (skill_dir / "SKILL.md").exists()
        assert (skill_dir / "agents" / "openai.yaml").exists()


def _expected_x_reach_wrapper_target(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(["x_reach", *parts])

