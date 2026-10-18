import math

import numpy as np
import pytest

from eval import signal_check as sc


@pytest.mark.slow
def test_evaluate_runs_end_to_end() -> None:
    storyline_match = sc._load(1000)
    noise = [sc._load(2200), sc._load(2201)]
    res = sc.evaluate([storyline_match], noise)
    rows = [r for v in res["storylines"].values() for r in v]
    assert len(rows) == len(storyline_match.storylines)
    for r in rows:
        assert 0.0 <= r["percentile"] <= 1.0 and not math.isnan(r["z"])


def test_templates_match_simulator_expected_signals() -> None:
    from sim.generate import simulate

    _, gt = simulate(1000)
    for sl in gt.storylines:
        key = sc._key(sl.model_dump())
        assert [s.metric for s in sl.expected_signals] == [m for m, _, _ in sc.TEMPLATES[key]]
        dirs = [1 if s.direction == "up" else -1 for s in sl.expected_signals]
        assert dirs == [d for _, _, d in sc.TEMPLATES[key]]


def test_robust_scale_ignores_heavy_tail() -> None:
    rng = np.random.default_rng(0)
    eff = rng.normal(0.0, 1.0, size=(2000, 1))
    eff[:40] = 50.0  # 2 % extreme outliers
    med, sd = sc.robust_scale(eff)
    assert abs(med[0]) < 0.15 and 0.85 < sd[0] < 1.2
    assert eff.std() > 5  # the classical sd would be dominated by the tail


def test_robust_scale_falls_back_when_mad_is_zero() -> None:
    eff = np.array([[0.0]] * 90 + [[1.0]] * 10)
    _, sd = sc.robust_scale(eff)
    assert sd[0] == pytest.approx(0.3, abs=1e-6)
