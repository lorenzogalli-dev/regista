"""Compares dev seed 1000 with output recorded on the author's machine (macOS ARM).

numpy does not promise bit-identical floating point across platforms. Events and match
metadata are expected to match exactly; tracking is compared exactly (informational) and
on a sample of frames within a small tolerance.
"""

import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from sim import io
from sim.generate import simulate
from sim.io import content_digest, write_match

DATA = Path(__file__).with_name("data")
RECORDED = DATA / "digest_m_1000.json"
SAMPLE = DATA / "tracking_sample_m_1000.json"
EVERY = 300  # one frame every 30 s
TOL_M = 0.05


def frame_sample(match_dir: Path) -> list[dict]:
    return list(itertools.islice(io.iter_tracking(match_dir), 0, None, EVERY))


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("xp")
    write_match(*simulate(1000), out / "out", out / "gt")
    return out / "out"


@pytest.mark.crossplatform
def test_events_and_meta_identical(generated: Path) -> None:
    recorded = json.loads(RECORDED.read_text())["digest"]
    got = content_digest(generated)
    for name in ("events.jsonl", "match.json"):
        assert got[name] == recorded[name], name


@pytest.mark.crossplatform
def test_tracking_sample_within_tolerance(generated: Path) -> None:
    ref = json.loads(SAMPLE.read_text())
    got = frame_sample(generated)
    assert [f["t_ms"] for f in got] == [f["t_ms"] for f in ref]
    worst = 0.0
    for a, b in zip(got, ref, strict=True):
        pa = {p["player_id"]: (p["x"], p["y"], p["speed_ms"]) for p in a["players"]}
        pb = {p["player_id"]: (p["x"], p["y"], p["speed_ms"]) for p in b["players"]}
        assert pa.keys() == pb.keys()
        diff = np.abs(np.array([pa[k] for k in pa]) - np.array([pb[k] for k in pa]))
        worst = max(worst, float(diff.max()))
    print(f"max abs difference on sampled frames: {worst:.3f}")
    assert worst <= TOL_M


@pytest.mark.crossplatform
@pytest.mark.xfail(
    strict=False,
    reason="Linux x86 and macOS ARM differ in a few last-decimal tracking values (2026-10-18)",
)
def test_tracking_identical(generated: Path) -> None:
    """Informational: exact equality of the full tracking file."""
    recorded = json.loads(RECORDED.read_text())["digest"]
    assert content_digest(generated)["tracking.jsonl"] == recorded["tracking.jsonl"]
