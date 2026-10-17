import math

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from metrics import bins as B
from metrics.data import from_dir
from metrics.store import MatchStore
from metrics.tools import MatchTools, PlayerId, TeamId
from sim import io
from sim.replay import merged
from tests.metrics_helpers import meta as tiny_meta

CUT_MS = 50 * 60_000


def _store(match_dir, upto_ms: int | None = None) -> MatchStore:
    st = MatchStore(io.read_meta(match_dir))
    for m in merged(match_dir, speed=1.0):
        if upto_ms is not None and m["data"]["t_ms"] > upto_ms:
            break
        if m["type"] == "frame":
            st.ingest_frame(m["data"])
        else:
            st.ingest_event(m["data"])
    return st


@pytest.fixture(scope="module")
def full(sample_dirs) -> MatchStore:
    return _store(sample_dirs[0])


@pytest.fixture(scope="module")
def partial(sample_dirs) -> MatchStore:
    return _store(sample_dirs[0], CUT_MS)


def test_store_matches_minute_bins(full, sample_dirs) -> None:
    b = B.build(from_dir(sample_dirs[0]))
    all_min = np.ones(b.n_minutes, dtype=bool)
    tools = MatchTools(full)
    for team in full.team_ids:
        ws = tools.get_window_stats(team, 0, 10**8)
        assert ws.field_tilt == pytest.approx(
            B.team_metric(b, "field_tilt", team, all_min), abs=1e-3
        )
        assert ws.pass_completion == pytest.approx(
            B.team_metric(b, "pass_completion", team, all_min), abs=1e-3
        )
        assert ws.ppda == pytest.approx(B.team_metric(b, "ppda", team, all_min), abs=1e-2)
        assert ws.possession_time_based == pytest.approx(
            B.team_metric(b, "possession", team, all_min), abs=1e-3
        )


def test_no_lookahead(full, partial) -> None:
    assert partial.now_ms <= CUT_MS
    a, p = MatchTools(full), MatchTools(partial)
    for team in full.team_ids:
        # asking the partial store about the future returns only what it has seen
        future = p.get_window_stats(team, 0, 10**8)
        assert future.end_ms == partial.now_ms + 1
        same = a.get_window_stats(team, 0, partial.now_ms + 1)
        assert future.model_dump() == same.model_dump()
    pid = full.player_ids[5]
    assert p.get_player_physical(pid, 0, 10**8) == a.get_player_physical(pid, 0, partial.now_ms + 1)
    assert all(t.t_ms <= CUT_MS for t in partial.triggers)
    ctx = p.get_moment_context(10**8)
    assert ctx.t_ms == partial.now_ms
    assert all(e.t_ms <= CUT_MS for e in ctx.recent_events)


def test_score_and_context(full) -> None:
    tools = MatchTools(full)
    ctx = tools.get_moment_context(full.now_ms)
    goals = [e for e in full.events if e["type"] == "goal"]
    assert sum(ctx.score.values()) == len(goals)
    assert ctx.period == 2


def _frames_store(positions: np.ndarray, speeds: np.ndarray, period_change_at: int) -> MatchStore:
    m = tiny_meta()
    st = MatchStore(m)
    pid = m.players[3].player_id
    others = [p.player_id for p in m.players if p.starter and p.player_id != pid]
    for i, ((x, y), s) in enumerate(zip(positions, speeds, strict=True)):
        period = 1 if i < period_change_at else 2
        players = [{"player_id": pid, "x": x, "y": y, "speed_ms": s}]
        home = m.home.team_id
        for o in others:
            ox = (
                30.0
                if (m.players[[p.player_id for p in m.players].index(o)].team_id == home)
                == (period == 1)
                else 75.0
            )
            players.append({"player_id": o, "x": ox, "y": 34.0, "speed_ms": 1.0})
        st.ingest_frame(
            {
                "t_ms": i * 100,
                "period": period,
                "ball": {"x": 52.5, "y": 34.0, "z": 0.0, "speed_ms": 0.0},
                "players": players,
            }
        )
    return st


def test_distance_skips_half_time_reset_and_jumps() -> None:
    n = 40
    xs = np.concatenate([np.arange(20) * 0.5, 80 + np.arange(20) * 0.5])  # reset between halves
    xs[10:] += np.where(np.arange(30) == 0, 0, 0)
    pos = np.stack([xs, np.full(n, 34.0)], axis=1)
    pos[5:, 0] += 3.0  # a 3.5 m step at frame 5: a data jump, not running
    st = _frames_store(pos, np.full(n, 5.0), period_change_at=20)
    pid = st.meta.players[3].player_id
    ph = st.physical(pid, 0, 10**8)
    # 38 valid steps of 0.5 m; the frame-5 jump and the half-time reset are skipped
    assert ph["distance_m"] == pytest.approx(0.5 * 37, abs=1e-3)


def test_sprint_needs_one_second() -> None:
    n = 200
    s = np.full(n, 3.0)
    s[20:29] = 8.0  # 0.9 s
    s[100:120] = 8.0  # 2 s
    pos = np.stack([np.cumsum(s) * 0.1, np.full(n, 34.0)], axis=1)
    st = _frames_store(pos, s, period_change_at=n)
    ph = st.physical(st.meta.players[3].player_id, 0, 10**8)
    assert ph["sprints"] == 1
    assert ph["top_speed_ms"] == pytest.approx(8.0)


def test_speed_trigger_cooldown() -> None:
    n = 3500  # 350 s
    s = np.full(n, 9.5)
    pos = np.stack([np.full(n, 40.0), np.full(n, 34.0)], axis=1)
    st = _frames_store(pos, s, period_change_at=n)
    times = [t.t_ms for t in st.triggers if t.kind == "speed"]
    assert len(times) == 2 and times[1] - times[0] >= 300_000


def test_ids_reject_anything_but_ids(full) -> None:
    for bad in ("../ground_truth", "data/ground_truth/m_1000/storylines.json", "t_hrb; rm", ""):
        with pytest.raises(ValidationError):
            TypeAdapter(TeamId).validate_python(bad)
        with pytest.raises(ValidationError):
            TypeAdapter(PlayerId).validate_python(bad)
    tools = MatchTools(full)
    with pytest.raises(ValueError):
        tools.get_window_stats("t_zzz", 0, 1000)
    with pytest.raises(ValueError):
        tools.get_player_physical("p_zzz_01", 0, 1000)


def test_values_are_finite_or_null(full) -> None:
    ws = MatchTools(full).get_window_stats(full.team_ids[0], 0, 10**8)
    for v in ws.model_dump().values():
        assert v is None or isinstance(v, str) or math.isfinite(v)
