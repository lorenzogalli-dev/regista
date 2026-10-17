import math

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
