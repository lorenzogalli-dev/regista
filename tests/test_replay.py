import asyncio
import itertools

from fastapi.testclient import TestClient

from api.main import app
from sim.replay import Pace, frame_stride, merged, replay


def test_frame_stride() -> None:
    assert (frame_stride(1), frame_stride(4), frame_stride(20)) == (1, 2, 10)


def test_merged_is_time_ordered_and_decimated(sample_dirs) -> None:
    out, _ = sample_dirs
    msgs = list(merged(out, speed=20, from_ms=60_000))
    ts = [m["data"]["t_ms"] for m in msgs]
    assert ts == sorted(ts) and ts[0] >= 60_000
    frames = [m["data"]["t_ms"] for m in msgs if m["type"] == "frame"]
    assert all((b - a) == 1000 for a, b in itertools.pairwise(frames))


def test_pacing_matches_speed(sample_dirs) -> None:
    out, _ = sample_dirs
    clock = {"t": 0.0}

    async def fake_sleep(s: float) -> None:
        clock["t"] += s

    async def run() -> list[dict]:
        return [
            m async for m in replay(out, 20.0, 5_000_000, now=lambda: clock["t"], sleep=fake_sleep)
        ]

    msgs = asyncio.run(run())
    assert msgs[0]["type"] == "meta" and msgs[-1]["type"] == "end"
    last_t = msgs[-2]["data"]["t_ms"]
    assert abs(clock["t"] - (last_t - 5_000_000) / 1000 / 20) < 0.05


def test_websocket_streams_events_and_frames(sample_dirs, monkeypatch) -> None:
    out, _ = sample_dirs
    monkeypatch.setenv("MATCH_DATA_DIR", str(out.parent))
    end = 5_580_000
    kinds: dict[str, int] = {}
    with (
        TestClient(app) as client,
        client.websocket_connect(f"/ws/replay/m_1000?speed=100&from_ms={end - 20_000}") as ws,
    ):
        while True:
            msg = ws.receive_json()
            kinds[msg["type"]] = kinds.get(msg["type"], 0) + 1
            if msg["type"] == "end":
                break
    assert kinds["meta"] == 1 and kinds["frame"] > 0 and kinds["event"] > 0


def test_websocket_unknown_match(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MATCH_DATA_DIR", str(tmp_path))
    with TestClient(app) as client, client.websocket_connect("/ws/replay/m_42") as ws:
        assert ws.receive_json()["type"] == "error"


def test_pace_holds_and_changes_rate(sample_dirs) -> None:
    out, _ = sample_dirs

    async def run() -> tuple[int, float]:
        pace = Pace(1.0)
        seen: list[int] = []

        async def consume() -> None:
            async for m in replay(out, 1.0, 5_000_000, pace=pace):
                if m["type"] in ("frame", "event"):
                    seen.append(m["data"]["t_ms"])

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.25)
        pace.set(0)
        await asyncio.sleep(0.05)
        held = len(seen)
        await asyncio.sleep(0.3)
        assert len(seen) == held, "a held stream must not advance"
        pace.set(50.0)
        await asyncio.sleep(0.4)
        task.cancel()
        return held, (seen[-1] - 5_000_000) / 1000

    held, reached_s = asyncio.run(run())
    assert held > 0
    # ~0.25 s at 1x plus ~0.4 s at 50x ≈ 20 s of match time (frames are not decimated).
    assert 12 < reached_s < 28
