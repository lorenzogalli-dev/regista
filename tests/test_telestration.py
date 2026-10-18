import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from metrics.telestration import highlights, run_telestration
from sim.schema import PITCH_LENGTH, PITCH_WIDTH

RUN = Path("data/recorded/r_m_1000_1ad2f33e.json")


def _run() -> dict:
    return json.loads(RUN.read_text())


def test_telestration_matches_the_cited_evidence(sample_dirs) -> None:
    out, _ = sample_dirs  # seed 1000: the match of the recorded run
    run = _run()
    tele = {t["moment_id"]: t for t in run_telestration(run, out)}
    assert [tele[m]["kind"] for m in ("mo_001", "mo_002", "mo_003", "mo_004")] == [
        "progressive",
        "territory",
        "long",
        "press",
    ]
    ev = {m["moment_id"]: m["explanation"]["evidence"] for m in run["moments"]}
    # The drawing counts the same thing the verified card cites.
    prog = next(e for e in ev["mo_001"] if e["metric"] == "progressive_passes")
    assert tele["mo_001"]["label"].startswith(f"{int(prog['after'])} progressive passes")
    assert len(tele["mo_001"]["arrows"]) == min(6, int(prog["after"]))
    length = next(e for e in ev["mo_003"] if e["metric"] == "avg_pass_length_m")
    assert f"average {length['after']:.1f} m" in tele["mo_003"]["label"]
    for t in tele.values():
        for z in t["zones"]:
            assert 0 <= z["x0"] < z["x1"] <= PITCH_LENGTH and 0 <= z["y0"] < z["y1"] <= PITCH_WIDTH
        assert t["show_at_ms"] > 0 and t["label"]


def test_highlights(sample_dirs) -> None:
    out, _ = sample_dirs
    h = highlights(out)
    kinds = {x["kind"] for x in h}
    assert "goal" in kinds and "shot" in kinds
    assert [x["t_ms"] for x in h] == sorted(x["t_ms"] for x in h)


def test_timeline_endpoint(sample_dirs, monkeypatch) -> None:
    out, _ = sample_dirs
    monkeypatch.setenv("MATCH_DATA_DIR", str(out.parent))
    monkeypatch.setenv("RUNS_DIR", str(RUN.parent))
    with TestClient(app) as client:
        r = client.get("/api/runs/r_m_1000_1ad2f33e/timeline")
        assert r.status_code == 200
        body = r.json()
        assert body["duration_ms"] == body["period_end_ms"][-1]
        assert len(body["telestration"]) == 4 and body["rejections"] == []
        assert client.get("/api/runs/r_m_1000_00000000/timeline").status_code == 404
