"""Compares a dev seed's content digest with the one recorded on the author's machine (macOS ARM).

numpy does not promise bit-identical floating point across platforms, so a mismatch is
reported, not treated as a failure of the same-platform determinism guarantee.
"""

import json
from pathlib import Path

import pytest

from sim.generate import simulate
from sim.io import content_digest, write_match

RECORDED = Path(__file__).with_name("data") / "digest_m_1000.json"


@pytest.mark.crossplatform
def test_digest_matches_recorded(tmp_path: Path) -> None:
    recorded = json.loads(RECORDED.read_text())
    write_match(*simulate(1000), tmp_path / "out", tmp_path / "gt")
    got = content_digest(tmp_path / "out")
    assert got == recorded["digest"], {"recorded_on": recorded["platform"], "got": got}
