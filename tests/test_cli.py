# -*- coding: utf-8 -*-
"""Tests for the Twitter-only CLI surface."""

import json

import pytest

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

    def test_collect_defaults_to_twitter_and_passes_search_filters(self, capsys, monkeypatch):
        captured = {}

        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                captured["channel"] = channel
                captured["kwargs"] = kwargs
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert (
            main(
                [
                    "collect",
                    "--operation",
                    "search",
                    "--input",
                    "OpenAI",
                    "--from",
                    "OpenAI",
                    "--min-likes",
                    "10",
                    "--min-views",
                    "1000",
                    "--json",
                ]
            )
            == 0
        )

        assert captured["channel"] == "twitter"
        assert captured["kwargs"]["from_user"] == "OpenAI"
        assert captured["kwargs"]["min_likes"] == 10
        assert captured["kwargs"]["min_views"] == 1000

    def test_collect_passes_originals_only_for_user_posts(self, capsys, monkeypatch):
        captured = {}

        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                captured["channel"] = channel
                captured["operation"] = operation
                captured["kwargs"] = kwargs
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert (
            main(
                [
                    "collect",
                    "--operation",
                    "user_posts",
                    "--input",
                    "OpenAI",
                    "--originals-only",
                    "--json",
                ]
            )
            == 0
        )

        assert captured["channel"] == "twitter"
        assert captured["operation"] == "user_posts"
        assert captured["kwargs"]["originals_only"] is True

    def test_search_shortcut_routes_to_collect(self, capsys, monkeypatch):
        captured = {}

        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                captured["channel"] = channel
                captured["operation"] = operation
                captured["value"] = value
                captured["kwargs"] = kwargs
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert main(["search", "OpenAI", "--min-views", "1000", "--json"]) == 0

        assert captured["channel"] == "twitter"
        assert captured["operation"] == "search"
        assert captured["value"] == "OpenAI"
        assert captured["kwargs"]["min_views"] == 1000

    def test_search_shortcut_passes_quality_profile(self, capsys, monkeypatch):
        captured = {}

        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                captured["kwargs"] = kwargs
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert main(["search", "OpenAI", "--quality-profile", "precision", "--json"]) == 0

        assert captured["kwargs"]["quality_profile"] == "precision"

    def test_hashtag_shortcut_routes_to_collect(self, capsys, monkeypatch):
        captured = {}

        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                captured["channel"] = channel
                captured["operation"] = operation
                captured["value"] = value
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert main(["hashtag", "OpenAI", "--json"]) == 0

        assert captured["channel"] == "twitter"
        assert captured["operation"] == "hashtag"
        assert captured["value"] == "OpenAI"

    def test_posts_shortcut_routes_to_user_posts_with_originals_only(self, capsys, monkeypatch):
        captured = {}

        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                captured["channel"] = channel
                captured["operation"] = operation
                captured["value"] = value
                captured["kwargs"] = kwargs
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)

        assert main(["posts", "OpenAI", "--limit", "5", "--originals-only", "--json"]) == 0

        assert captured["channel"] == "twitter"
        assert captured["operation"] == "user_posts"
        assert captured["value"] == "OpenAI"
        assert captured["kwargs"]["limit"] == 5
        assert captured["kwargs"]["originals_only"] is True

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

    def test_collect_save_is_quiet_about_missing_metadata_by_default(self, capsys, monkeypatch):
        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)
        monkeypatch.setattr("agent_reach.cli.save_collection_result", lambda *args, **kwargs: None)

        assert (
            main(
                [
                    "collect",
                    "--operation",
                    "search",
                    "--input",
                    "OpenAI",
                    "--save",
                    "evidence.jsonl",
                    "--run-id",
                    "run-1",
                    "--json",
                ]
            )
            == 0
        )

        captured = capsys.readouterr()
        assert "[WARN] evidence ledger save used without evidence metadata" not in captured.err

    def test_collect_can_warn_about_missing_metadata_when_requested(self, capsys, monkeypatch):
        class _FakeClient:
            def collect(self, channel, operation, value, **kwargs):
                return {
                    "ok": True,
                    "channel": channel,
                    "operation": operation,
                    "items": [],
                    "raw": None,
                    "meta": {"count": 0},
                    "error": None,
                }

        monkeypatch.setattr("agent_reach.cli.AgentReachClient", _FakeClient)
        monkeypatch.setattr("agent_reach.cli.save_collection_result", lambda *args, **kwargs: None)

        assert (
            main(
                [
                    "collect",
                    "--operation",
                    "search",
                    "--input",
                    "OpenAI",
                    "--save",
                    "evidence.jsonl",
                    "--run-id",
                    "run-1",
                    "--warn-missing-evidence-metadata",
                    "--json",
                ]
            )
            == 0
        )

        captured = capsys.readouterr()
        assert "[WARN] evidence ledger save used without evidence metadata" in captured.err

    def test_plan_candidates_passes_new_filtering_args(self, tmp_path, capsys, monkeypatch):
        captured = {}
        topic_fit_path = tmp_path / "topic-fit.json"
        topic_fit_path.write_text(
            json.dumps({"topic_fit": {"required_any_terms": ["codex"]}}),
            encoding="utf-8",
        )

        def fake_build_candidates_payload(*args, **kwargs):
            captured["kwargs"] = kwargs
            return {
                "command": "plan candidates",
                "summary": {"candidate_count": 0, "returned": 0},
                "candidates": [],
            }

        monkeypatch.setattr("agent_reach.cli.build_candidates_payload", fake_build_candidates_payload)

        assert (
            main(
                [
                    "plan",
                    "candidates",
                    "--input",
                    "evidence.jsonl",
                    "--max-per-author",
                    "2",
                    "--prefer-originals",
                    "--drop-noise",
                    "--drop-title-duplicates",
                    "--require-query-match",
                    "--topic-fit",
                    str(topic_fit_path),
                    "--min-seen-in",
                    "2",
                    "--sort-by",
                    "quality_score",
                    "--json",
                ]
            )
            == 0
        )

        assert captured["kwargs"]["max_per_author"] == 2
        assert captured["kwargs"]["prefer_originals"] is True
        assert captured["kwargs"]["drop_noise"] is True
        assert captured["kwargs"]["drop_title_duplicates"] is True
        assert captured["kwargs"]["require_query_match"] is True
        assert captured["kwargs"]["topic_fit"] == {"required_any_terms": ["codex"]}
        assert captured["kwargs"]["min_seen_in"] == 2
        assert captured["kwargs"]["sort_by"] == "quality_score"

    def test_plan_candidates_rejects_invalid_sort_by_choice(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "plan",
                    "candidates",
                    "--input",
                    "evidence.jsonl",
                    "--sort-by",
                    "importance",
                    "--json",
                ]
            )

        assert exc_info.value.code == 2
        assert "invalid choice" in capsys.readouterr().err

    def test_batch_cli_passes_pacing_args(self, tmp_path, capsys, monkeypatch):
        plan_path = tmp_path / "plan.json"
        plan_path.write_text('{"queries":[]}', encoding="utf-8")
        captured = {}

        def fake_run_batch_plan(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return {"ok": True, "command": "batch", "summary": {}}, 0

        monkeypatch.setattr("agent_reach.cli.run_batch_plan", fake_run_batch_plan)

        assert (
            main(
                [
                    "batch",
                    "--plan",
                    str(plan_path),
                    "--save",
                    str(tmp_path / "ledger.jsonl"),
                    "--query-delay",
                    "1.5",
                    "--query-jitter",
                    "0.25",
                    "--throttle-cooldown",
                    "12",
                    "--throttle-error-limit",
                    "2",
                    "--json",
                ]
            )
            == 0
        )

        assert json.loads(capsys.readouterr().out)["command"] == "batch"
        assert captured["kwargs"]["query_delay_seconds"] == 1.5
        assert captured["kwargs"]["query_jitter_seconds"] == 0.25
        assert captured["kwargs"]["throttle_cooldown_seconds"] == 12.0
        assert captured["kwargs"]["throttle_error_limit"] == 2

    def test_collect_spec_cli_passes_pacing_args(self, tmp_path, capsys, monkeypatch):
        spec_path = tmp_path / "mission.json"
        spec_path.write_text('{"queries":["OpenAI"]}', encoding="utf-8")
        captured = {}

        def fake_run_mission_spec(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return {"ok": True, "command": "collect spec"}

        monkeypatch.setattr("agent_reach.cli.run_mission_spec", fake_run_mission_spec)

        assert (
            main(
                [
                    "collect",
                    "--spec",
                    str(spec_path),
                    "--query-delay",
                    "1",
                    "--query-jitter",
                    "0.5",
                    "--throttle-cooldown",
                    "30",
                    "--throttle-error-limit",
                    "3",
                    "--json",
                ]
            )
            == 0
        )

        assert json.loads(capsys.readouterr().out)["command"] == "collect spec"
        assert captured["kwargs"]["query_delay_seconds"] == 1.0
        assert captured["kwargs"]["query_jitter_seconds"] == 0.5
        assert captured["kwargs"]["throttle_cooldown_seconds"] == 30.0
        assert captured["kwargs"]["throttle_error_limit"] == 3

    def test_schema_judge_result_json(self, capsys):
        assert main(["schema", "judge-result", "--json"]) == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["title"] == "X Reach JudgeResult"
        assert "fallback_keep" in payload["properties"]["decision"]["enum"]

    def test_uninstall_dry_run_mentions_twitter_cleanup(self, capsys):
        assert main(["uninstall", "--dry-run"]) == 0
        output = capsys.readouterr().out
        assert "uv tool uninstall twitter-cli" in output

