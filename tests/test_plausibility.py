"""SPEC §4 plausibility on the 20 dev seeds: means within spec ranges, wide bands per match."""

import numpy as np
import pytest

from sim.plausibility import summarise_seeds
from sim.seeds import DEV_SEEDS

MEAN_RANGES = {
    "passes": (900, 1100),
    "shots": (20, 30),
    "goals": (1, 4),
    "pass_completion": (0.75, 0.88),
    "tackles": (35, 55),  # attempted, incl. failed; not a SPEC §4 target, agreed 2026-10-17
}
MATCH_BANDS = {
    "passes": (800, 1250),
    "shots": (10, 45),
    "goals": (0, 9),
    "pass_completion": (0.70, 0.90),
    "max_player_speed": (8.5, 10.0),
    "tackles": (25, 80),
}


@pytest.fixture(scope="module")
def rows():
    return summarise_seeds(list(DEV_SEEDS), workers=4)


@pytest.mark.slow
@pytest.mark.parametrize("metric", sorted(MEAN_RANGES))
def test_mean_in_spec_range(rows, metric: str) -> None:
    lo, hi = MEAN_RANGES[metric]
    mean = float(np.mean([getattr(r, metric) for r in rows]))
    assert lo <= mean <= hi, f"{metric} mean {mean:.3f} not in [{lo}, {hi}]"


@pytest.mark.slow
@pytest.mark.parametrize("metric", sorted(MATCH_BANDS))
def test_each_match_in_band(rows, metric: str) -> None:
    lo, hi = MATCH_BANDS[metric]
    bad = [(r.seed, getattr(r, metric)) for r in rows if not lo <= getattr(r, metric) <= hi]
    assert not bad, f"{metric} outside [{lo}, {hi}]: {bad}"
