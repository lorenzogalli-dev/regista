"""Deploy data: only public match files and recorded runs reach Blob Storage or the container."""

import json
from pathlib import Path

import pytest

from api.data_sync import UnexpectedBlob, check_name
from infra.upload_data import manifest
from sim import io


@pytest.mark.parametrize(
    "name",
    [
        "generated/m_1000/" + io.GT_FILE,
        "ground_truth/m_1000/" + io.GT_FILE,
        "generated/m_1000/../x/match.json",
        "generated/m_1000/notes.txt",
        "recorded/../secrets.json",
        ".env",
    ],
)
def test_unexpected_blobs_are_refused(name: str) -> None:
    with pytest.raises(UnexpectedBlob):
        check_name(name)


def test_manifest_has_runs_and_their_public_match_files(sample_dirs, tmp_path: Path) -> None:
    out, gt = sample_dirs
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "r_m_1000_0123abcd.json").write_text(json.dumps({"match_id": "m_1000"}))
    names = [n for n, _ in manifest(runs, out.parent)]
    assert names == [
        "recorded/r_m_1000_0123abcd.json",
        "generated/m_1000/match.json",
        "generated/m_1000/events.jsonl",
        "generated/m_1000/tracking.jsonl.gz",
        "generated/m_1000/tracking.idx.json",
    ]
    assert not any(io.GT_FILE in n for n in names)
    assert (gt / "m_1000" / io.GT_FILE).is_file()  # it exists locally, and is not uploaded
