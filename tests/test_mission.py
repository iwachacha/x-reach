# -*- coding: utf-8 -*-
"""Tests for mission-spec collection runtime."""

from __future__ import annotations

import json

from agent_reach.mission import build_mission_plan_payload, run_mission_spec
from agent_reach.results import build_item, build_result
from x_reach.cli import main


def _write_spec(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_mission_plan_normalizes_review_style_spec(tmp_path):
    spec_path = tmp_path / "mission.json"
    _write_spec(
        spec_path,
        {
            "objective": "new feature X complaints",
            "queries": ["feature X bug"],
            "time_range": {"since": "2026-03-01", "until": "2026-04-15"},
            "languages": ["ja"],
            "target_posts": 4,
            "quality_profile": "research_high_precision",
            "exclude": {"drop_retweets": True, "min_views": 100},
            "retention": {"raw_mode": "minimal", "item_text_mode": "snippet", "item_text_max_chars": 120},
        },
    )

    payload = build_mission_plan_payload(spec_path, output_dir=tmp_path / "out", run_id="run-test")
    query = payload["batch_plan"]["queries"][0]

    assert payload["quality_profile"] == "precision"
    assert payload["query_count"] == 1
    assert query["input"] == "feature X bug"
    assert query["lang"] == "ja"
    assert query["since"] == "2026-03-01"
    assert query["until"] == "2026-04-15"
    assert query["limit"] == 4
    assert query["exclude"] == ["retweets", "replies"]
    assert query["min_views"] == 100
    assert query["raw_mode"] == "minimal"
    assert query["item_text_mode"] == "snippet"
    assert query["item_text_max_chars"] == 120


def test_mission_run_writes_raw_canonical_ranked_and_summary(tmp_path):
    spec_path = tmp_path / "mission.json"
    output_dir = tmp_path / "mission-output"
    _write_spec(
        spec_path,
        {
            "objective": "OpenAI X signal",
            "queries": ["OpenAI", "OpenAI latest"],
            "target_posts": 2,
            "quality_profile": "balanced",
            "exclude": {"keywords": ["lottery"], "drop_low_content_posts": False},
            "diversity": {"max_posts_per_author": 2},
            "retention": {"raw_mode": "full", "item_text_mode": "full"},
        },
    )
    calls = []

    class _FakeClient:
        def collect(self, channel, operation, value, **kwargs):
            calls.append({"channel": channel, "operation": operation, "value": value, "kwargs": kwargs})
            if value == "OpenAI latest":
                items = [
                    _post(
                        "3",
                        "alice",
                        "OpenAI latest practical report with concrete details and screenshots",
                        likes=1000,
                    )
                ]
            else:
                items = [
                    _post("1", "alice", "OpenAI useful detailed post from a practitioner", likes=25),
                    _post("2", "bob", "OpenAI lottery announcement that should be excluded", likes=500),
                ]
            return build_result(
                ok=True,
                channel=channel,
                operation=operation,
                items=items,
                raw={"value": value, "kwargs": kwargs},
                meta={"input": value, "count": len(items), "query_tokens": ["openai"]},
                error=None,
            )

    payload = run_mission_spec(
        spec_path,
        output_dir=output_dir,
        run_id="run-mission",
        client_factory=_FakeClient,
    )

    assert payload["ok"] is True
    assert payload["summary"]["items_seen"] == 3
    assert payload["summary"]["canonical_items"] == 3
    assert payload["summary"]["ranked_candidates"] == 2
    assert payload["summary"]["filter_drop_counts"]["excluded_keyword"] == 1
    assert (output_dir / "raw.jsonl").exists()
    assert (output_dir / "canonical.jsonl").exists()
    assert (output_dir / "ranked.jsonl").exists()
    assert (output_dir / "summary.md").exists()

    ranked = [
        json.loads(line)
        for line in (output_dir / "ranked.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["id"] for item in ranked] == ["3", "1"]
    assert ranked[0]["rank"] == 1
    assert ranked[0]["quality_score"] > ranked[1]["quality_score"]
    assert calls[0]["kwargs"]["raw_mode"] == "full"
    assert calls[0]["kwargs"]["item_text_mode"] == "full"


def test_collect_spec_dry_run_cli(tmp_path, capsys):
    spec_path = tmp_path / "mission.json"
    _write_spec(spec_path, {"queries": ["OpenAI"], "target_posts": 1})

    assert main(["collect", "--spec", str(spec_path), "--dry-run", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "collect spec"
    assert payload["dry_run"] is True
    assert payload["query_count"] == 1


def _post(item_id, author, text, *, likes):
    return build_item(
        item_id=item_id,
        kind="post",
        title=text[:80],
        url=f"https://x.com/{author}/status/{item_id}",
        text=text,
        author=author,
        published_at="2026-04-10T00:00:00Z",
        source="twitter",
        extras={
            "timeline_item_kind": "original",
            "author_handle": author,
            "post_id": item_id,
            "conversation_id": f"thread-{item_id}",
            "likes": likes,
        },
        engagement={"likes": likes},
        identifiers={
            "author_handle": author,
            "post_id": item_id,
            "conversation_id": f"thread-{item_id}",
        },
    )
