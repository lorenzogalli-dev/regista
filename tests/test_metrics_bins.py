import numpy as np
import pytest

from metrics import bins as B
from metrics.data import from_dir, from_sim
from tests.metrics_helpers import P1_END, match, meta

M = meta()
HOME, AWAY = M.home.team_id, M.away.team_id
H9 = next(
    p.player_id for p in M.players if p.team_id == HOME and p.position not in ("GK",) and p.starter
)
ALL = np.ones(6, dtype=bool)


def _pass(t, team, x, y, ex, ey, outcome="complete", player=None, recipient=None):
    return {
        "t_ms": t,
        "type": "pass",
        "team_id": team,
        "x": x,
        "y": y,
        "end_x": ex,
        "end_y": ey,
        "outcome": outcome,
        "player_id": player,
        "recipient_id": recipient,
    }


def test_direction_inferred_from_positions() -> None:
    md = match([])
    assert md.direction(HOME, 1) == 1 and md.direction(HOME, 2) == -1
    assert md.direction(AWAY, 1) == -1 and md.direction(AWAY, 2) == 1


def test_pass_completion_and_length() -> None:
    b = B.build(
        match([_pass(1000, HOME, 10, 34, 20, 34), _pass(2000, HOME, 10, 34, 40, 34, "incomplete")])
    )
    assert B.team_metric(b, "pass_completion", HOME, ALL) == 0.5
    assert B.team_metric(b, "avg_pass_length", HOME, ALL) == 20.0


def test_ppda_counts_zone_only() -> None:
    ev = [
        _pass(1000, AWAY, 100, 34, 90, 34),  # away attacks -x in P1: own 60 % is x > 42
        _pass(2000, AWAY, 60, 34, 50, 34),
        _pass(3000, AWAY, 20, 34, 10, 34),  # away's attacking half, outside its own 60 %
        {"t_ms": 4000, "type": "tackle", "team_id": HOME, "x": 70, "y": 34, "outcome": "won"},
        {"t_ms": 5000, "type": "tackle", "team_id": HOME, "x": 30, "y": 34, "outcome": "won"},
    ]
    b = B.build(match(ev))
    assert B.team_metric(b, "ppda", HOME, ALL) == 2.0  # 2 passes / 1 action in zone


def test_field_tilt_uses_attacking_frame_and_switches_at_half() -> None:
    ev = [
        {
            "t_ms": 1000,
            "type": "carry",
            "team_id": HOME,
            "x": 80,
            "y": 34,
            "end_x": 82,
            "end_y": 34,
        },
        {
            "t_ms": P1_END + 1000,
            "type": "carry",
            "team_id": HOME,
            "x": 25,
            "y": 34,
            "end_x": 20,
            "end_y": 34,
        },
        {
            "t_ms": 2000,
            "type": "carry",
            "team_id": AWAY,
            "x": 20,
            "y": 34,
            "end_x": 18,
            "end_y": 34,
        },
        {
            "t_ms": 3000,
            "type": "carry",
            "team_id": AWAY,
            "x": 60,
            "y": 34,
            "end_x": 58,
            "end_y": 34,
        },
    ]
    b = B.build(match(ev))
    assert B.team_metric(b, "field_tilt", HOME, ALL) == pytest.approx(2 / 3)


def test_time_based_possession() -> None:
    ev = [
        {"t_ms": 0, "type": "kickoff", "team_id": HOME, "x": 52.5, "y": 34},
        {"t_ms": 60_000, "type": "possession_change", "team_id": AWAY, "x": 50, "y": 34},
        {"t_ms": 90_000, "type": "possession_change", "team_id": HOME, "x": 50, "y": 34},
    ]
    b = B.build(match(ev))
    # home: 0-60 s and 90-360 s = 330 s of 360 s
    assert B.team_metric(b, "possession", HOME, ALL) == pytest.approx(330 / 360)
    assert B.team_metric(b, "possession", AWAY, ALL) == pytest.approx(30 / 360)


@pytest.mark.parametrize(
    ("sx", "ex", "expected"),
    [
        (10, 39, False),
        (10, 40, True),
        (45, 59, False),
        (45, 60, True),
        (60, 69, False),
        (60, 70, True),
    ],
)
def test_progressive_rule(sx, ex, expected) -> None:
    assert B.is_progressive(sx, ex) is expected


def test_sprint_needs_one_second() -> None:
    T = 6 * 600
    s = np.full(T, 3.0)
    s[100:109] = 8.0  # 0.9 s above threshold after smoothing edges -> not a sprint
    s[1000:1020] = 8.0  # 2 s -> one sprint
    s[2000:2015] = 8.0  # 1.5 s -> one sprint
    b = B.build(match([], speed={H9: s}))
    assert b.player["sprints"][b.player_idx(H9)].sum() == 2


def test_top_speed_is_smoothed() -> None:
    T = 6 * 600
    s = np.full(T, 3.0)
    s[500] = 11.0  # a single-frame spike is not a top speed
    b = B.build(match([], speed={H9: s}))
    assert B.player_metric(b, "top_speed", H9, ALL) < 5.0


def test_files_and_memory_give_same_bins(sample, sample_dirs) -> None:
    out, _ = sample_dirs
    a, c = B.build(from_sim(sample[0])), B.build(from_dir(out))
    for k in B.TEAM_FIELDS:
        assert np.allclose(a.team[k], c.team[k]), k
    for k in B.PLAYER_FIELDS:
        assert np.allclose(a.player[k], c.player[k]), k
