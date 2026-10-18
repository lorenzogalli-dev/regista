"""Fit the Detector's noise reference (`agents/detector_params.json`).

Runs the live candidate statistics (`agents.candidates`) at every check time on matches generated
with zero storylines (calibration-control seeds 2200-2249) and stores, per kind and signal, the
median and robust scale of the signed effect plus the 95th / 99th percentile of the resulting z.
Only public match data is read (no ground truth exists for these seeds).

Then reports how many candidates the rule produces per match on held-out no-storyline matches
(2250-2274) and on dev seeds, which drives the cost estimate of a pipeline run.

    uv run python -m eval.fit_detector
"""

import argparse
import json
import statistics
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from agents import candidates as C
from metrics.cli import load_store
from metrics.store import MatchStore
from sim.generate import simulate
from sim.io import write_match
from sim.seeds import CALIBRATION_CONTROL_SEEDS, DEV_SEEDS

FIT_SEEDS = CALIBRATION_CONTROL_SEEDS[:50]
CHECK_SEEDS = CALIBRATION_CONTROL_SEEDS[50:75]
MAD_TO_SD = 1.4826


def _store(seed: int) -> MatchStore:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        write_match(*simulate(seed), out / "m", out / "gt")
        return load_store(out / "m")


def _effects(seed: int) -> dict[str, list[list[float]]]:
    st = _store(seed)
    rows: dict[str, list[list[float]]] = {k: [] for k in C.SIGNALS}
    t = C.MIN_BEFORE_MIN * C.MIN_MS
    while t <= st.now_ms:
        for kind, minutes in C.WINDOW_MIN.items():
            start = t - minutes * C.MIN_MS
            if start < C.MIN_BEFORE_MIN * C.MIN_MS:
                continue
            for team, player in C.subjects(st, kind, t):
                eff = C.raw_effects(st, kind, team, player, start, t)
                vals = [d * (w - b) for _, _, d, w, b in eff]
                if not any(np.isnan(vals)):
                    rows[kind].append(vals)
        t += C.CHECK_MS
    return rows


def _count(seed: int) -> int:
    st = _store(seed)
    finder = C.CandidateFinder(st)
    return len(finder.poll())


def fit(rows: dict[str, list[list[float]]]) -> dict[str, Any]:
    kinds: dict[str, Any] = {}
    for kind, r in rows.items():
        eff = np.array(r)
        med = np.median(eff, axis=0)
        mad = MAD_TO_SD * np.median(np.abs(eff - med), axis=0)
        scale = np.where(mad > 1e-9, mad, eff.std(axis=0)) + 1e-9
        z = (eff - med) / scale
        kinds[kind] = {
            "n": len(r),
            "median": med.round(6).tolist(),
            "scale": scale.round(6).tolist(),
            "p95": np.percentile(z, 95, axis=0).round(4).tolist(),
            "p99": np.percentile(z, 99, axis=0).round(4).tolist(),
        }
    return {
        "note": "Noise reference for agents.candidates; fitted on no-storyline seeds 2200-2249.",
        "window_min": C.WINDOW_MIN,
        "check_ms": C.CHECK_MS,
        "kinds": kinds,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval.fit_detector")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    with ProcessPoolExecutor(a.workers) as pool:
        merged: dict[str, list[list[float]]] = {k: [] for k in C.SIGNALS}
        for rows in pool.map(_effects, FIT_SEEDS):
            for k, v in rows.items():
                merged[k].extend(v)
        C.PARAMS_PATH.write_text(json.dumps(fit(merged), indent=1) + "\n")
        C.params.cache_clear()
        noise = list(pool.map(_count, CHECK_SEEDS))
        dev = list(pool.map(_count, DEV_SEEDS))
    print(f"wrote {C.PARAMS_PATH}")
    print(
        f"candidates per match: no-storyline holdout mean {statistics.mean(noise):.1f} "
        f"(range {min(noise)}-{max(noise)}), dev mean {statistics.mean(dev):.1f} "
        f"(range {min(dev)}-{max(dev)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
