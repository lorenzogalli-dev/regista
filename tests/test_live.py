"""Recorded and live streams share one message vocabulary (fake client, no pacing)."""

import asyncio
from collections import Counter

import pytest

from agents import live
from agents.config import Settings
from agents.run import run_match

FAKE = Settings(provider="fake", run_budget_eur=1e9)


async def _instant(_: float) -> None:
    await asyncio.sleep(0)


@pytest.fixture(scope="module")
def live_messages(sample_dirs) -> list[dict]:
    msgs: list[dict] = []

    async def send(m: dict) -> None:
        msgs.append(m)

    asyncio.run(
        live.live_session(sample_dirs[0], 20.0, send, FAKE, live.DailyCap(1000), False, _instant)
    )
    return msgs


def test_live_session_streams_tier0_tier1_and_pipeline(live_messages) -> None:
    kinds = Counter(m["type"] for m in live_messages)
    assert live_messages[0]["type"] == "run" and live_messages[0]["data"]["kind"] == "Live"
    assert kinds["frame"] and kinds["event"] and kinds["overlay"] and kinds["pipeline"]
    cards = [m["data"] for m in live_messages if m["type"] == "overlay" and m["data"]["tier"] == 1]
    states = Counter(c["payload"].get("state") for c in cards if c["kind"] == "moment_card")
    assert states["pending"] and states["verified"]
    # Each verified card replaces a pending template shown earlier in the stream.
    order = [c["overlay_id"] for c in cards]
    for c in cards:
        if c["payload"].get("state") == "verified":
            assert order.index(c["payload"]["replaces"]) < order.index(c["overlay_id"])
    stages = {m["stage"] for m in live_messages if m["type"] == "pipeline"}
    assert {"candidate", "detector", "analyst#1", "verifier:code", "result"} <= stages


def test_live_cap_pauses_ai_cards(sample_dirs) -> None:
    msgs: list[dict] = []

    async def send(m: dict) -> None:
        msgs.append(m)

    asyncio.run(
        live.live_session(sample_dirs[0], 20.0, send, FAKE, live.DailyCap(0), False, _instant)
    )
    assert any(m["type"] == "notice" and "cap" in m["detail"] for m in msgs)
    assert not any(m["type"] == "pipeline" for m in msgs)
    assert any(m["type"] == "overlay" for m in msgs)  # tier 0 never waits for agents


def test_recorded_stream_replays_saved_overlays_in_time_order(sample_dirs) -> None:
    run = asyncio.run(run_match(sample_dirs[0], "full", FAKE, use_mcp=False))
    assert run["overlays"]

    async def collect() -> list[dict]:
        out = []
        stream = live.recorded_stream(run, sample_dirs[0], 100.0, 0)
        async for m in stream:
            out.append(m)
        return out

    import sim.replay

    real = sim.replay.asyncio.sleep
    sim.replay.asyncio.sleep = _instant  # type: ignore[assignment]
    try:
        msgs = asyncio.run(collect())
    finally:
        sim.replay.asyncio.sleep = real  # type: ignore[assignment]
    assert msgs[0]["data"]["kind"] == "Recorded agent run"
    overlays = [m["data"] for m in msgs if m["type"] == "overlay"]
    assert len(overlays) == len(run["overlays"])
    t = [m["data"]["t_ms"] for m in msgs if m["type"] in ("frame", "event")]
    assert t == sorted(t)
    assert msgs[-1]["type"] == "end"


def test_rebuilt_overlays_match_the_recorded_ones(sample_dirs) -> None:
    from agents.run import rebuild_overlays

    run = asyncio.run(run_match(sample_dirs[0], "full", FAKE, use_mcp=False))
    rebuilt = rebuild_overlays(run, sample_dirs[0])
    assert [o["overlay_id"] for o in rebuilt] == [o["overlay_id"] for o in run["overlays"]]
    pending = [o for o in rebuilt if o["payload"].get("state") == "pending"]
    verified = {
        o["payload"]["replaces"]: o for o in rebuilt if o["payload"].get("state") == "verified"
    }
    assert pending and verified
    for p in pending:
        # The template's numbers come from the same windows as the verified card's evidence.
        assert p["payload"]["text"].startswith("Last ")
