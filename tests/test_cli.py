# -*- coding: utf-8 -*-
"""Tests for the Twitter-only CLI surface."""

import json

import agent_reach.cli as cli
from agent_reach.cli import main


class TestCLI:
    def test_version(self, capsys):
        assert main(["version"]) == 0
        assert "X Reach v" in capsys.readouterr().out

    def test_no_command_shows_help(self):
        assert main([]) == 0

    def test_parse_twitter_cookie_input_separate_values(self):
        auth_token, ct0 = cli._parse_twitter_cookie_input("token123 ct0abc")
        assert auth_token == "token123"
        assert ct0 == "ct0abc"

    def test_parse_twitter_cookie_input_cookie_header(self):
        auth_token, ct0 = cli._parse_twitter_cookie_input(
            "auth_token=token123; ct0=ct0abc; other=value"
        )
        assert auth_token == "token123"
        assert ct0 == "ct0abc"

    def test_safe_install_lists_twitter_commands(self, capsys, monkeypatch):
        monkeypatch.setattr("agent_reach.cli.find_command", lambda _name: None)
        assert main(["install", "--safe", "--channels=twitter"]) == 0
        output = capsys.readouterr().out
        assert "uv tool install twitter-cli" in output
        assert "x-reach skill --install" in output
        assert "GitHub.cli" not in output

    def test_install_dry_run_json(self, capsys, monkeypatch):
        monkeypatch.setattr("agent_reach.cli.find_command", lambda _name: None)
        assert main(["install", "--dry-run", "--json", "--channels=twitter"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["command"] == "install"
        assert payload["mode"] == "dry-run"
        assert payload["selected_channels"] == ["twitter"]
        assert payload["channel_specific_setup_channels"] == ["twitter"]
        assert "uv tool install twitter-cli" in payload["commands"]
        assert payload["mcp_config"] is None

    def test_install_parses_all_channels(self, monkeypatch):
        calls = []

        monkeypatch.setattr(cli, "_install_skill", lambda: [])
        monkeypatch.setattr(cli, "_detect_environment", lambda: "local")
        monkeypatch.setattr(
            cli,
            "_install_twitter_deps",
            lambda: calls.append("twitter") or True,
        )
        monkeypatch.setattr(
            "agent_reach.doctor.check_all",
            lambda _config: {
                "twitter": {
                    "status": "ok",
                    "name": "twitter",
                    "description": "Twitter/X",
                    "message": "ok",
                    "backends": [],
                }
            },
        )
        monkeypatch.setattr("agent_reach.doctor.format_report", lambda _results: "report")

        assert main(["install", "--channels=all"]) == 0
        assert calls == ["twitter"]

    def test_doctor_json(self, capsys, monkeypatch):
        monkeypatch.setattr(
            "agent_reach.doctor.check_all",
            lambda _config, probe=False: {
                "twitter": {
                    "name": "twitter",
                    "description": "Twitter/X",
                    "status": "ok",
                    "message": "ready",
                }
            },
        )
        assert main(["doctor", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["ready"] == 1
        assert payload["channels"][0]["name"] == "twitter"

    def test_collect_json_success(self, capsys, monkeypatch):
        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [{"id": "1", "title": "Example", "url": value}],
                    "raw": kwargs,
                    "meta": {"count": 1},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert (
            main(
                [
                    "collect",
                    "--channel",
                    "twitter",
                    "--operation",
                    "search",
                    "--input",
                    "OpenAI",
                    "--json",
                ]
            )
            == 0
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["channel"] == "twitter"

    def test_collect_unknown_channel_returns_exit_2(self, capsys, monkeypatch):
        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                return {
                    "ok": False,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"input": value},
                    "error": {
                        "code": "unknown_channel",
                        "message": "Unknown channel",
                        "details": {},
                    },
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert (
            main(
                [
                    "collect",
                    "--channel",
                    "nope",
                    "--operation",
                    "search",
                    "--input",
                    "value",
                ]
            )
            == 2
        )

    def test_collect_max_text_chars_adds_text_mode_snippet(self, capsys, monkeypatch):
        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [
                        {
                            "id": "1",
                            "title": "Example",
                            "url": value,
                            "text": "abcdefghijklmnopqrstuvwxyz",
                        }
                    ],
                    "raw": None,
                    "meta": {"count": 1},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert (
            main(
                [
                    "collect",
                    "--channel",
                    "twitter",
                    "--operation",
                    "search",
                    "--input",
                    "OpenAI",
                    "--max-text-chars",
                    "5",
                ]
            )
            == 0
        )
        output = capsys.readouterr().out
        assert "abcde..." in output

    def test_collect_json_item_text_mode_none_omits_text(self, capsys, monkeypatch):
        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [{"id": "1", "title": "Example", "url": value, "text": "abcdefghijklmnopqrstuvwxyz"}],
                    "raw": None,
                    "meta": {"count": 1},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert (
            main(
                [
                    "collect",
                    "--channel",
                    "twitter",
                    "--operation",
                    "search",
                    "--input",
                    "OpenAI",
                    "--json",
                    "--item-text-mode",
                    "none",
                ]
            )
            == 0
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["items"][0]["text"] is None

    def test_uninstall_dry_run_mentions_twitter_cleanup(self, capsys):
        assert main(["uninstall", "--dry-run"]) == 0
        output = capsys.readouterr().out
        assert "uv tool uninstall twitter-cli" in output

