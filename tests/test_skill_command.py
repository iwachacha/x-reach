# -*- coding: utf-8 -*-
"""Tests for skill install and uninstall helpers."""

from agent_reach.cli import _candidate_skill_roots, _install_skill, _uninstall_skill
from agent_reach.integrations.codex import PACKAGED_SKILL_NAMES


def test_install_skill_prefers_codex_home(monkeypatch, tmp_path):
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr("agent_reach.cli.Path.home", lambda: tmp_path)

    installed = _install_skill()

    expected = [codex_home / "skills" / skill_name for skill_name in PACKAGED_SKILL_NAMES]
    assert installed == expected
    for target in expected:
        assert (target / "SKILL.md").exists()
        assert (target / "agents" / "openai.yaml").exists()


def test_uninstall_skill_removes_known_locations(monkeypatch, tmp_path):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr("agent_reach.cli.Path.home", lambda: tmp_path)

    targets = []
    for skill_name in PACKAGED_SKILL_NAMES:
        target = tmp_path / ".codex" / "skills" / skill_name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("test", encoding="utf-8")
        targets.append(target)

    removed = _uninstall_skill()

    assert removed == targets
    for target in targets:
        assert not target.exists()


def test_candidate_skill_roots_do_not_include_legacy_agent_dirs(monkeypatch, tmp_path):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr("agent_reach.cli.Path.home", lambda: tmp_path)

    roots = _candidate_skill_roots()
    rendered = [str(root) for root in roots]

    assert any(path.endswith(".codex\\skills") or path.endswith(".codex/skills") for path in rendered)
    assert any(path.endswith(".agents\\skills") or path.endswith(".agents/skills") for path in rendered)
    assert all(".claude" not in path for path in rendered)
    assert all(".openclaw" not in path for path in rendered)
