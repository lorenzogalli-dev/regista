import math

import numpy as np
import pytest

from metrics import control, counters, models
from metrics.fit import auc, logistic_fit, xt_grid


def test_logistic_fit_recovers_coefficients() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(20_000, 2))
    p = 1 / (1 + np.exp(-(0.5 + 1.5 * X[:, 0] - 1.0 * X[:, 1])))
    y = (rng.random(20_000) < p).astype(float)
    m = logistic_fit(X, y)
    w = np.array(m["coef"]) / np.array(m["std"])  # back to raw-feature scale
    assert w == pytest.approx([1.5, -1.0], abs=0.08)


def test_auc() -> None:
    assert auc(np.array([0, 0, 1, 1.0]), np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert auc(np.array([1, 1, 0, 0.0]), np.array([0.1, 0.2, 0.8, 0.9])) == 0.0


def test_xg_monotone_and_bounded() -> None:
    near = models.xg(models.shot_features(96.0, 34.0, False))
    far = models.xg(models.shot_features(80.0, 34.0, False))
    head = models.xg(models.shot_features(96.0, 34.0, True))
    wide = models.xg(models.shot_features(100.0, 10.0, False))
    assert 0 < far < near < 1
    assert head < near
    assert wide < near


def test_pass_difficulty_monotone() -> None:
    short = models.pass_difficulty(np.array([10.0, 5.0, 0.0, 0.0]))
    long = models.pass_difficulty(np.array([40.0, 5.0, 0.0, 0.0]))
    crowded = models.pass_difficulty(np.array([10.0, 5.0, 2.0, 0.0]))
    assert 0 < short < long < 1
    assert short < crowded


def test_xt_grid_is_highest_near_goal() -> None:
    grid = np.array(models.params()["xt"]["grid"])
    assert grid.shape == (models.XT_COLS, models.XT_ROWS)
    assert grid[-1].max() == grid.max()
    assert grid[0].mean() < grid[-1].mean()
    assert models.xt(100.0, 34.0) > models.xt(20.0, 34.0)


def test_xt_value_iteration_on_tiny_grid() -> None:
    # 2x1 grid: zone 1 always shoots (goal prob 0.5); zone 0 always moves to zone 1.
    shot = np.array([[0.0], [10.0]])
    goal = np.array([[0.0], [5.0]])
    move = np.array([[10.0], [0.0]])
    trans = np.zeros((2, 1, 2, 1))
    trans[0, 0, 1, 0] = 10.0
    x = xt_grid(shot, goal, move, trans)
    assert x[1, 0] == pytest.approx(0.5)
    assert x[0, 0] == pytest.approx(0.5)


def test_control_index_range_and_direction() -> None:
    ref = models.params()["control"]
    mid = {k: v["median"] for k, v in ref.items()}
    assert models.control_index(mid) == pytest.approx(50.0)
    more = {**mid, "possession_length_s": mid["possession_length_s"] * 3}
    assert models.control_index(more) > 50.0
    chaotic = {**mid, "turnovers_per_min": mid["turnovers_per_min"] * 3}
    assert models.control_index(chaotic) < 50.0
    assert models.control_index({**mid, "event_rate_cv": math.nan}) is None
    extreme = {k: v["median"] + 100 * v["scale"] for k, v in ref.items()}
    assert 0.0 <= models.control_index(extreme) <= 100.0


def test_time_based_possession_ms() -> None:
    changes = [(0, "a"), (10_000, "b"), (25_000, "a")]
    assert counters.possession_ms(changes, 0, 30_000) == {"a": 15_000, "b": 15_000}
    assert counters.possession_ms(changes, 5_000, 12_000) == {"a": 5_000, "b": 2_000}


def test_control_components_simple() -> None:
    def to_att(team, period, x, y):
        return (x, y) if team == "a" else (105 - x, 68 - y)

    events = [
        {"t_ms": 1_000, "type": "pass", "team_id": "a", "period": 1, "x": 60.0, "y": 30.0},
        {"t_ms": 30_000, "type": "pass", "team_id": "b", "period": 1, "x": 80.0, "y": 30.0},
        {"t_ms": 45_000, "type": "pass", "team_id": "a", "period": 1, "x": 40.0, "y": 30.0},
    ]
    changes = [(0, "a"), (20_000, "b"), (40_000, "a")]
    c = control.components(events, changes, "a", 0, 60_000, to_att)
    assert c["possession_length_s"] == pytest.approx(20.0)  # 20 s, then 20 s clipped at 60 s
    assert c["turnovers_per_min"] == pytest.approx(2.0)
    assert c["end_in_opp_half_share"] == 1.0  # first possession ended at x=60 (opp half)
