"""Seek index for tracking files: starting late reads the same frames as a full scan."""

import gzip
import json
import shutil
from pathlib import Path

import pytest

from sim import io


@pytest.mark.parametrize("from_ms", [1, 59_999, 60_000, 2_031_050, 4_898_500])
def test_seek_matches_full_scan(sample_dirs, from_ms: int) -> None:
    out, _ = sample_dirs
    full = [f for f in io.iter_tracking(out) if f["t_ms"] >= from_ms]
    assert list(io.iter_tracking(out, from_ms)) == full


def test_one_member_per_minute_and_plain_gzip(sample_dirs) -> None:
    out, _ = sample_dirs
    index = json.loads((out / io.INDEX_FILE).read_text())
    firsts = [t for t, _ in index["members"]]
    assert firsts == sorted(firsts)
    assert len({t // io.MEMBER_MS for t in firsts}) == len(firsts)
    assert index["size"] == (out / io.TRACKING_FILE).stat().st_size
    with gzip.open(out / io.TRACKING_FILE, "rt") as f:  # any gzip reader sees one stream
        assert sum(1 for _ in f) == sum(1 for _ in io.iter_tracking(out))


def test_stale_index_is_ignored(sample_dirs, tmp_path: Path) -> None:
    out, _ = sample_dirs
    d = tmp_path / "m"
    shutil.copytree(out, d)
    (d / io.INDEX_FILE).write_text(json.dumps({"size": -1, "members": [[0, 12345]]}))
    assert list(io.iter_tracking(d, 600_000)) == list(io.iter_tracking(out, 600_000))


def test_reindex_keeps_content(sample_dirs, tmp_path: Path) -> None:
    out, _ = sample_dirs
    d = tmp_path / "m"
    shutil.copytree(out, d)
    # The layout before the index: one gzip member, no index file.
    with gzip.open(out / io.TRACKING_FILE, "rb") as f:
        content = f.read()
    (d / io.TRACKING_FILE).write_bytes(gzip.compress(content, mtime=0))
    (d / io.INDEX_FILE).unlink()
    io.reindex_tracking(d)
    assert io.content_digest(d) == io.content_digest(out)
    assert (d / io.TRACKING_FILE).read_bytes() == (out / io.TRACKING_FILE).read_bytes()
    assert (d / io.INDEX_FILE).read_text() == (out / io.INDEX_FILE).read_text()
