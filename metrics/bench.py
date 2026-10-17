"""Ingest and tool-query cost during a replay at a given speed (default 20x).

    uv run python -m metrics.bench m_1000 --speed 20 --seconds 60

At 20x the stream carries 200 tracking frames per wall second, so each frame has a
5 ms budget. The live ingest consumes every frame (not the decimated client stream).
Reported per frame: JSON parse + ingest time. Tool queries run once per wall second.
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

from metrics.store import MatchStore
from metrics.tools import MatchTools
from sim import io
from sim.replay import merged


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


async def run(match_dir: Path, speed: float, seconds: float, start_ms: int) -> dict[str, float]:
    meta = io.read_meta(match_dir)
    # Raw JSON lines, as a live feed would deliver them; frame stride 1 = every frame.
    raw = [(m["type"], json.dumps(m["data"])) for m in merged(match_dir, speed=1.0, from_ms=0)]
    st = MatchStore(meta)
    tools = MatchTools(st)
    home = meta.home.team_id
    frame_ms: list[float] = []
    event_ms: list[float] = []
    query_ms: list[float] = []
    max_lag_ms = 0.0
    # Warm up to start_ms without pacing (a live store would already hold this state).
    i = 0
    while i < len(raw):
        typ, line = raw[i]
        d = json.loads(line)
        if d["t_ms"] >= start_ms:
            break
        (st.ingest_frame if typ == "frame" else st.ingest_event)(d)
        i += 1
    t0 = time.perf_counter()
    next_query = t0 + 1.0
    while i < len(raw):
        typ, line = raw[i]
        a = time.perf_counter()
        d = json.loads(line)
        due = t0 + (d["t_ms"] - start_ms) / 1000 / speed
        if due - t0 > seconds:
            break
        if due > a:
            await asyncio.sleep(due - a)
            a = time.perf_counter()
        max_lag_ms = max(max_lag_ms, (a - due) * 1000)
        if typ == "frame":
            st.ingest_frame(d)
            frame_ms.append((time.perf_counter() - a) * 1000)
        else:
            st.ingest_event(d)
            event_ms.append((time.perf_counter() - a) * 1000)
        if time.perf_counter() >= next_query:
            q = time.perf_counter()
            tools.get_moment_context(st.now_ms)
            tools.get_window_stats(home, max(0, st.now_ms - 15 * 60_000), st.now_ms + 1)
            query_ms.append((time.perf_counter() - q) * 1000)
            next_query += 1.0
        i += 1
    wall = time.perf_counter() - t0
    return {
        "speed": speed,
        "wall_s": wall,
        "match_minutes_covered": (st.now_ms - start_ms) / 60_000,
        "frames": len(frame_ms),
        "frames_per_wall_s": len(frame_ms) / wall,
        "frame_budget_ms": 1000 / (10 * speed),
        "frame_ms_p50": statistics.median(frame_ms),
        "frame_ms_p99": _pct(frame_ms, 0.99),
        "frame_ms_max": max(frame_ms),
        "events": len(event_ms),
        "event_ms_p50": statistics.median(event_ms) if event_ms else 0.0,
        "event_ms_p99": _pct(event_ms, 0.99) if event_ms else 0.0,
        "queries": len(query_ms),
        "query_ms_p50": statistics.median(query_ms) if query_ms else 0.0,
        "query_ms_max": max(query_ms) if query_ms else 0.0,
        "max_lag_behind_schedule_ms": max_lag_ms,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m metrics.bench")
    ap.add_argument("match_id")
    ap.add_argument("--speed", type=float, default=20.0)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--start-ms", type=int, default=30 * 60_000)
    ap.add_argument("--data-dir", default=os.environ.get("MATCH_DATA_DIR", "data/generated"))
    a = ap.parse_args(argv)
    res = asyncio.run(run(Path(a.data_dir) / a.match_id, a.speed, a.seconds, a.start_ms))
    print(json.dumps({k: round(v, 3) for k, v in res.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
