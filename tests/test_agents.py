"""D3 agent pipeline, end to end with the fake client (no model calls, no cost)."""

import asyncio
import os
from dataclasses import replace
from pathlib import Path

import pytest

from agents import candidates as C
from agents import evidence as E
from agents.config import Settings
from agents.estimate import estimate
from agents.fake import _verifier
from agents.run import run_match
from metrics.cli import load_store
from sim import io
from sim.replay import merged

FAKE = Settings(provider="fake", run_budget_eur=1e9)


@pytest.fixture(scope="module")
def match_dir(sample_dirs) -> Path:
    return sample_dirs[0]


@pytest.fixture(scope="module")
def full_run(match_dir) -> dict:
    return asyncio.run(run_match(match_dir, "full", FAKE, use_mcp=True))


def test_candidates_never_look_ahead(match_dir) -> None:
    """Streaming ingestion and a fully ingested store give the same candidates."""
    live = C.CandidateFinder(load_store(match_dir).__class__(io.read_meta(match_dir)))
    streamed = []
    for m in merged(match_dir, speed=1.0):
        st = live.store
        (st.ingest_frame if m["type"] == "frame" else st.ingest_event)(m["data"])
        if st.now_ms >= live.next_check:
            streamed += live.poll()
    full = load_store(match_dir)
    replay = C.CandidateFinder(full)
    after = []
    while replay.next_check <= full.now_ms:
        after += replay.check(replay.next_check)
        replay.next_check += C.CHECK_MS
    key = [(c.kind, c.t_ms, c.team_id, c.player_id) for c in streamed]
    assert streamed and key == [(c.kind, c.t_ms, c.team_id, c.player_id) for c in after]
    for c in streamed:
        assert c.window_end_ms == c.t_ms
        assert sum(s.over_p95 for s in c.signals) >= 2 or len(c.signals) == 1


def test_full_pipeline_publishes_verified_moments(full_run) -> None:
    assert full_run["candidates"] == len(full_run["moments"]) > 0
    published = [m for m in full_run["moments"] if m["status"] == "published"]
    assert published
    for m in published:
        x = m["explanation"]
        assert (x["evidence"] and x["mechanism_tag"] in C.SIGNALS) or x["mechanism_tag"] in (
            "pressing_spell",
            "momentum_shift",
            "tactical_switch",
            "player_arc",
            "none",
        )
        assert {p["persona_id"] for p in m["personas"]} == {
            f"{mode}_{lang}"
            for mode in ("analyst", "casual", "player_focus")
            for lang in ("en", "it", "es")
        }
        assert m["caption"]["text"] and m["cue"]["duration_ms"] >= 4000
        stages = [s["stage"] for s in m["stages"]]
        assert stages[:2] == ["detector", "analyst#1"] and "verifier:code" in stages
    usage = full_run["usage"]
    assert usage["provider"] == "fake" and usage["estimated"]
    assert set(usage["by_agent"]) == {
        "detector",
        "analyst",
        "verifier",
        "narrator",
        "persona",
        "director",
    }


def test_analyst_reaches_metrics_over_mcp(full_run) -> None:
    # The fake Analyst makes one MCP tool call per attempt: two model calls per attempt.
    attempts = sum(m["attempts"] for m in full_run["moments"])
    assert full_run["usage"]["by_agent"]["analyst"]["calls"] == 2 * attempts


def test_published_evidence_recomputes(match_dir, full_run) -> None:
    from agents.schemas import Evidence
    from metrics.tools import MatchTools

    tools = MatchTools(load_store(match_dir))
    for m in full_run["moments"]:
        if m["status"] == "published":
            for e in m["explanation"]["evidence"]:
                assert E.recompute(tools, Evidence(**e)) is None


def test_hallucinated_number_is_rejected_then_dropped(match_dir, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_HALLUCINATE", "1")
    run = asyncio.run(run_match(match_dir, "eval", FAKE, use_mcp=False))
    assert run["moments"]
    for m in run["moments"]:
        if m["detector"]["keep"]:
            assert m["status"] == "dropped" and m["attempts"] == 2
            assert "tool says" in m["rejection"]
            assert [s["stage"] for s in m["stages"]].count("verifier:code") == 2


def test_eval_mode_stops_after_verifier(match_dir) -> None:
    run = asyncio.run(run_match(match_dir, "eval", FAKE, use_mcp=False))
    assert {m["status"] for m in run["moments"]} <= {"approved", "dropped"}
    assert set(run["usage"]["by_agent"]) <= {"detector", "analyst", "verifier"}


def test_budget_cap_stops_the_run(match_dir) -> None:
    run = asyncio.run(
        run_match(match_dir, "full", replace(FAKE, run_budget_eur=0.0), use_mcp=False)
    )
    assert run["budget_stopped"] and "budget" in run["budget_stopped"]
    assert run["usage"]["calls"] == 0


def test_failed_agent_falls_back_to_template(match_dir, monkeypatch) -> None:
    from agents import pipeline

    real = pipeline.Desk.ask

    async def flaky(self, name, prompt, fmt):
        if name == "narrator":
            raise TimeoutError
        return await real(self, name, prompt, fmt)

    monkeypatch.setattr(pipeline.Desk, "ask", flaky)
    run = asyncio.run(run_match(match_dir, "full", FAKE, use_mcp=False))
    published = [m for m in run["moments"] if m["status"] == "published"]
    assert published and all(m["fallbacks"] == ["caption"] for m in published)
    assert all(m["caption"]["text"] == m["explanation"]["claim"][:140] for m in published)
    assert any(s["outcome"] == "timeout" for m in published for s in m["stages"])


def test_verifier_text_check_flags_stray_numbers() -> None:
    ev = [{"before": 0.214, "after": 0.732}]
    ok = _verifier({"claim": "Field tilt rose from 21% to 73%.", "evidence": ev})
    bad = _verifier({"claim": "Field tilt rose from 21% to 91%.", "evidence": ev})
    assert ok.consistent and not bad.consistent and "91" in bad.problems[0]


def test_estimate_prices_reasoning_and_fast_roles(full_run) -> None:
    est = estimate([full_run], Settings(provider="fake"))
    lo, hi = est["eur_range"]
    assert 0 < lo < est["eur_point"] < hi
    assert est["per_agent"]["analyst"]["eur"] > est["per_agent"]["detector"]["eur"]


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
def test_run_saved_to_postgres(full_run) -> None:
    import psycopg

    from agents.persist import save_run

    url = os.environ["DATABASE_URL"]
    save_run(url, full_run)
    with psycopg.connect(url) as conn:
        n = conn.execute(
            "SELECT count(*) FROM run_moments WHERE run_id = %s", (full_run["run_id"],)
        ).fetchone()
        assert n is not None and n[0] == len(full_run["moments"])
