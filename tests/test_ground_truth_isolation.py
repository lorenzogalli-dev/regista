from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from sim import io

ROOT = Path(__file__).resolve().parents[1]


def test_output_dir_never_contains_ground_truth(sample_dirs) -> None:
    out, gt = sample_dirs
    assert not list(out.rglob(io.GT_FILE))
    assert (gt / "m_1000" / io.GT_FILE).is_file()


@pytest.mark.parametrize(
    ("out", "gt"),
    [("data/x", "data/x"), ("data/gt/m_1", "data/gt"), ("data/out", "data/out/gt")],
)
def test_overlapping_dirs_rejected(tmp_path: Path, out: str, gt: str) -> None:
    with pytest.raises(io.GroundTruthLeak):
        io.check_separation(tmp_path / out, tmp_path / gt)


def test_api_cannot_reach_ground_truth(sample_dirs, monkeypatch) -> None:
    out, _ = sample_dirs
    monkeypatch.setenv("MATCH_DATA_DIR", str(out.parent))
    client = TestClient(app)
    assert [m["match_id"] for m in client.get("/api/matches").json()] == ["m_1000"]
    for bad in ("..%2Fground_truth%2Fm_1000", "m_1000%2F..%2F..%2Fground_truth", "storylines"):
        assert client.get(f"/api/matches/{bad}").status_code == 404
    body = client.get("/api/matches/m_1000").text
    assert "storyline" not in body and "canonical_explanation" not in body


def test_container_never_ships_or_mounts_ground_truth() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY data" not in dockerfile and "ground_truth" not in dockerfile.replace(
        "# Hidden ground truth is never copied into the image.", ""
    )
    compose = (ROOT / "docker-compose.yml").read_text()
    mounts = [line for line in compose.splitlines() if line.strip().startswith("- ./")]
    assert mounts and not any("ground_truth" in m for m in mounts)
    assert "data/ground_truth/" in (ROOT / ".gitignore").read_text()
