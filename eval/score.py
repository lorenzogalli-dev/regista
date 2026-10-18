"""Score pipeline runs against the hidden storylines (offline; reads ground truth).

    uv run python -m eval.score data/runs/r_m_1000_*.json ...

- Storyline recall: share of storylines with at least one approved explanation that falls in
  the window (± 3 min), for the right team (and actor, for player storylines), with a matching
  `mechanism_tag`. Reported per type. "Falls in" = the midpoint of the explanation's window is
  inside the storyline window ± 3 min (an explanation is emitted at the end of the window it
  describes); `recall_strict` uses the emission time instead.
- Explanation precision: share of approved explanations that match a storyline.
- Evidence validity: share of approved evidence items that a second, independent path agrees
  with: minute bins built from the match files (metrics.bins), not the live store the Verifier
  queries. Items it cannot recompute (xT, control index, distance, off-minute windows) are
  counted separately as unchecked.
- Hallucination rate: share of analysed moments with a Verifier rejection, plus share of
  approved evidence failing the independent check.
- Latency: p50 / p95 per stage and from candidate to approval.
"""

import argparse
import json
import statistics
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from metrics import bins as B
from metrics.data import from_dir
from sim.io import GT_FILE

WINDOW_SLACK_MS = 180_000
MIN_MS = 60_000
TEAM_MAP = {
    "possession_time_based": "possession",
    "field_tilt": "field_tilt",
    "ppda": "ppda",
    "pass_completion": "pass_completion",
    "avg_pass_length_m": "avg_pass_length",
    "width_m": "width",
}
PLAYER_MAP = {"touches": "touches", "progressive_passes": "prog_passes", "sprints": "sprints"}
APPROVED = ("approved", "published")


def storyline_key(sl: dict[str, Any]) -> str:
    return str(sl["type"])


@cache
def match_bins(match_dir: str) -> B.MinuteBins:
    return B.build(from_dir(Path(match_dir)))


def _mask(b: B.MinuteBins, start: int, end: int) -> np.ndarray | None:
    if start % MIN_MS or end % MIN_MS or end <= start:
        return None
    m = np.zeros(b.n_minutes, dtype=bool)
    m[start // MIN_MS : end // MIN_MS] = True
    return m


def independent(b: B.MinuteBins, ev: dict[str, Any], which: str) -> float | None:
    start, end = ev[f"{which}_start_ms"], ev[f"{which}_end_ms"]
    mask = _mask(b, start, end)
    if mask is None:
        return None
    if ev["tool"] == "get_window_stats" and ev["metric"] in TEAM_MAP:
        v = B.team_metric(b, TEAM_MAP[ev["metric"]], ev["subject"], mask)
        return None if np.isnan(v) else v
    if ev["tool"] == "get_player_physical":
        pi = b.player_idx(ev["subject"])
        if ev["metric"] in PLAYER_MAP:
            return float(b.player[PLAYER_MAP[ev["metric"]]][pi, mask].sum())
        if ev["metric"] == "minutes_on_pitch":
            return float(b.player["on_frames"][pi, mask].sum()) / B.FRAMES_PER_MIN
    return None


def check_evidence(b: B.MinuteBins, ev: dict[str, Any]) -> str:
    """'ok', 'bad' or 'unchecked'."""
    for which in ("before", "after"):
        v = independent(b, ev, which)
        if v is None:
            return "unchecked"
        tol = max(0.002, 0.02 * abs(v)) if ev["tool"] == "get_window_stats" else 0.51
        if abs(v - ev[which]) > tol:
            return "bad"
    return "ok"


def matches(m: dict[str, Any], sl: dict[str, Any], strict: bool = False) -> bool:
    x = m["explanation"]
    if m["status"] not in APPROVED or x is None:
        return False
    c = m["candidate"]
    t = c["t_ms"] if strict else (c["window_start_ms"] + c["window_end_ms"]) // 2
    if not (sl["start_ms"] - WINDOW_SLACK_MS <= t <= sl["end_ms"] + WINDOW_SLACK_MS):
        return False
    if x["mechanism_tag"] != sl["type"] or x["team_id"] != sl["team_id"]:
        return False
    return not (sl["type"] == "player_arc" and not set(x["player_ids"]) & set(sl["actors"]))


def score(runs: list[dict[str, Any]], data_dir: Path, gt_dir: Path) -> dict[str, Any]:
    recall: dict[str, list[bool]] = defaultdict(list)
    strict: list[bool] = []
    approved = matched = 0
    ev_counts = {"ok": 0, "bad": 0, "unchecked": 0}
    analysed = rejected = 0
    stage_ms: dict[str, list[int]] = defaultdict(list)
    for run in runs:
        gt = json.loads((gt_dir / run["match_id"] / GT_FILE).read_text())
        sls = gt["storylines"]
        b = match_bins(str(data_dir / run["match_id"]))
        for sl in sls:
            recall[storyline_key(sl)].append(any(matches(m, sl) for m in run["moments"]))
            strict.append(any(matches(m, sl, strict=True) for m in run["moments"]))
        for m in run["moments"]:
            for s in m["stages"]:
                stage_ms[s["stage"].split("#")[0]].append(s["ms"])
            if m["attempts"]:
                analysed += 1
                rejected += any(s["outcome"] == "rejected" for s in m["stages"])
            if m["status"] in APPROVED:
                approved += 1
                matched += any(matches(m, sl) for sl in sls)
                for ev in m["explanation"]["evidence"]:
                    ev_counts[check_evidence(b, ev)] += 1
    checked = ev_counts["ok"] + ev_counts["bad"]
    all_recall = [h for v in recall.values() for h in v]

    def pct(xs: list[int], q: float) -> int:
        return int(np.percentile(xs, q)) if xs else 0

    return {
        "matches": [r["match_id"] for r in runs],
        "storylines": len(all_recall),
        "recall": round(statistics.mean(all_recall), 3) if all_recall else None,
        "recall_strict": round(statistics.mean(strict), 3) if strict else None,
        "recall_by_type": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(recall.items())},
        "approved": approved,
        "precision": round(matched / approved, 3) if approved else None,
        "evidence": ev_counts,
        "evidence_validity": round(ev_counts["ok"] / checked, 3) if checked else None,
        "verifier_rejection_rate": round(rejected / analysed, 3) if analysed else None,
        "latency_ms": {k: {"p50": pct(v, 50), "p95": pct(v, 95)} for k, v in stage_ms.items()},
        "cost_eur": round(sum(r["usage"]["cost_eur"] for r in runs), 4),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval.score")
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--data-dir", type=Path, default=Path("data/generated"))
    ap.add_argument("--gt-dir", type=Path, default=Path("data/ground_truth"))
    a = ap.parse_args(argv)
    runs = [json.loads(p.read_text()) for p in a.runs]
    print(json.dumps(score(runs, a.data_dir, a.gt_dir), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
