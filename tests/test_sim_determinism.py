import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from sim.generate import simulate
from sim.io import content_digest, write_match


def test_same_seed_same_output_in_process(sample) -> None:
    again, gt2 = simulate(1000)
    first, gt1 = sample
    assert again.events == first.events
    assert gt1 == gt2
    for name in ("t_ms", "ball", "pos", "speed", "slot_player"):
        assert np.array_equal(getattr(again, name), getattr(first, name)), name


def test_files_byte_identical_across_processes(sample_dirs, tmp_path: Path) -> None:
    """Fresh interpreters with different hash seeds must write byte-identical files."""
    out, _ = sample_dirs
    expected = {p.name: p.read_bytes() for p in out.iterdir()}
    for hashseed in ("1", "12345"):
        target = tmp_path / f"h{hashseed}"
        env = {**os.environ, "PYTHONHASHSEED": hashseed}
        subprocess.run(
            [
                sys.executable,
                "-m",
                "sim.cli",
                "generate",
                "--seed",
                "1000",
                "--out",
                str(target / "out"),
                "--gt-dir",
                str(target / "gt"),
            ],
            check=True,
            env=env,
            capture_output=True,
        )
        got = {p.name: p.read_bytes() for p in (target / "out").iterdir()}
        assert got.keys() == expected.keys()
        for name in expected:
            assert got[name] == expected[name], name


def test_different_seeds_differ(sample) -> None:
    other, _ = simulate(1001)
    assert other.events != sample[0].events


def test_digest_is_stable(sample_dirs, tmp_path: Path) -> None:
    out, _ = sample_dirs
    copy = tmp_path / "copy"
    write_match(*simulate(1000), copy, tmp_path / "gt")
    assert content_digest(copy) == content_digest(out)
    assert set(json.loads(json.dumps(content_digest(out)))) == {
        "match.json",
        "events.jsonl",
        "tracking.jsonl",
    }
