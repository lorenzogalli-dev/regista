from pathlib import Path

import pytest

from sim.engine import SimResult
from sim.generate import simulate
from sim.io import write_match
from sim.schema import GroundTruth

SAMPLE_SEED = 1000


@pytest.fixture(scope="session")
def sample() -> tuple[SimResult, GroundTruth]:
    return simulate(SAMPLE_SEED)


@pytest.fixture(scope="session")
def sample_dirs(sample, tmp_path_factory) -> tuple[Path, Path]:
    """(public match dir, ground-truth root) for the sample match, written once per session."""
    root = tmp_path_factory.mktemp("sim")
    out, gt = root / "generated" / "m_1000", root / "ground_truth"
    write_match(*sample, out, gt)
    return out, gt
