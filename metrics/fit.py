"""Fit pass difficulty, xG, xT and control-index references on calibration seeds.

    uv run python -m metrics.fit [--workers 8]

Uses only public match data (events and tracking) of calibration seeds 2000-2199; no
ground truth is read. Writes metrics/params.json.
"""

import argparse
import json
import math
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import numpy as np

from metrics import control
from metrics.data import MatchData, from_sim
from metrics.models import (
    PARAMS_PATH,
    XT_COLS,
    XT_ROWS,
    Snapshot,
    pass_features,
    shot_features,
    xt_zone,
)
from sim.generate import simulate
from sim.schema import TICK_MS
from sim.seeds import CALIBRATION_SEEDS

WINDOW_MS = 5 * 60_000


def snapshot(md: MatchData, t_ms: int) -> Snapshot:
    """Tracking frame just before t_ms (the state in which the action was chosen)."""
    i = max(0, min(len(md.t_ms) - 1, t_ms // TICK_MS - 1))
    return Snapshot(md.pos[i], md.player_ids, md.player_team, md.player_index)


def collect(seed: int) -> dict[str, Any]:
    md = from_sim(simulate(seed)[0])
    passes_x, passes_y, shots_x, shots_y = [], [], [], []
    shot_zone = np.zeros((XT_COLS, XT_ROWS))
    goal_zone = np.zeros((XT_COLS, XT_ROWS))
    move_zone = np.zeros((XT_COLS, XT_ROWS))
    trans = np.zeros((XT_COLS, XT_ROWS, XT_COLS, XT_ROWS))
    for e in md.events:
        team = e["team_id"]
        if e["type"] == "pass":
            passes_x.append(pass_features(e, snapshot(md, e["t_ms"])))
            passes_y.append(0.0 if e["outcome"] == "complete" else 1.0)
        if e["type"] in ("pass", "carry"):
            ax, ay = md.to_attacking(team, e["period"], e["x"], e["y"])
            z = xt_zone(ax, ay)
            move_zone[z] += 1
            if e["type"] == "carry" or e["outcome"] == "complete":
                ex, ey = md.to_attacking(team, e["period"], e["end_x"], e["end_y"])
                trans[z + xt_zone(ex, ey)] += 1
        if e["type"] == "shot":
            ax, ay = md.to_attacking(team, e["period"], e["x"], e["y"])
            shots_x.append(shot_features(ax, ay, e["qualifiers"].get("body_part") == "head"))
            goal = 1.0 if e["outcome"] == "goal" else 0.0
            shots_y.append(goal)
            z = xt_zone(ax, ay)
            shot_zone[z] += 1
            goal_zone[z] += goal
    changes = [
        (e["t_ms"], e["team_id"])
        for e in md.events
        if e["type"] in ("kickoff", "possession_change")
    ]
    comps = []
    for start in range(0, md.duration_ms - WINDOW_MS + 1, WINDOW_MS):
        for team in md.team_ids:
            comps.append(
                control.components(
                    md.events, changes, team, start, start + WINDOW_MS, md.to_attacking
                )
            )
    return {
        "passes_x": np.array(passes_x),
        "passes_y": np.array(passes_y),
        "shots_x": np.array(shots_x),
        "shots_y": np.array(shots_y),
        "shot_zone": shot_zone,
        "goal_zone": goal_zone,
        "move_zone": move_zone,
        "trans": trans,
        "control": comps,
    }


def logistic_fit(X: np.ndarray, y: np.ndarray, l2: float = 1e-3, iters: int = 50) -> dict[str, Any]:
    """Standardised logistic regression by iteratively reweighted least squares."""
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    w = np.zeros(Z.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-Z @ w))
        W = p * (1 - p) + 1e-9
        H = Z.T @ (Z * W[:, None]) + l2 * np.eye(len(w))
        step = np.linalg.solve(H, Z.T @ (y - p) - l2 * w)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    p = 1.0 / (1.0 + np.exp(-Z @ w))
    return {
        "intercept": float(w[0]),
        "coef": w[1:].tolist(),
        "mean": mu.tolist(),
        "std": sd.tolist(),
        "n": len(y),
        "base_rate": float(y.mean()),
        "auc": auc(y, p),
        "log_loss": float(-np.mean(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12))),
    }


def auc(y: np.ndarray, p: np.ndarray) -> float:
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def xt_grid(shot: np.ndarray, goal: np.ndarray, move: np.ndarray, trans: np.ndarray) -> np.ndarray:
    total = shot + move
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.where(total > 0, shot / total, 0.0)
        m = np.where(total > 0, move / total, 0.0)
        g = np.where(shot > 0, goal / shot, 0.0)
        T = np.where(move[..., None, None] > 0, trans / move[..., None, None], 0.0)
    x = np.zeros_like(s)
    for _ in range(100):
        new = s * g + m * np.einsum("abcd,cd->ab", T, x)
        if np.abs(new - x).max() < 1e-9:
            x = new
            break
        x = new
    return x


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m metrics.fit")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        parts = list(pool.map(collect, CALIBRATION_SEEDS))
    pX = np.vstack([p["passes_x"] for p in parts])
    py = np.concatenate([p["passes_y"] for p in parts])
    pd_model = logistic_fit(pX, py)
    z = pd_model["intercept"] + ((pX - pd_model["mean"]) / pd_model["std"]) @ np.array(
        pd_model["coef"]
    )
    difficulty = 1.0 / (1.0 + np.exp(-z))
    # Trigger threshold: the hardest 2 % of completed passes on calibration data.
    pd_model["difficult_pass_threshold"] = float(np.percentile(difficulty[py == 0], 98))
    sX = np.vstack([p["shots_x"] for p in parts])
    sy = np.concatenate([p["shots_y"] for p in parts])
    grid = xt_grid(
        *(sum(p[k] for p in parts) for k in ("shot_zone", "goal_zone", "move_zone", "trans"))
    )
    comps = [c for p in parts for c in p["control"]]
    ref = {}
    for name in (
        "possession_length_s",
        "turnovers_per_min",
        "event_rate_cv",
        "end_in_opp_half_share",
    ):
        v = np.array([c[name] for c in comps])
        v = v[~np.isnan(v)]
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        ref[name] = {
            "median": float(med),
            "scale": float(max((q3 - q1) / 1.349, 1e-6)),
            "n": len(v),
        }
    out: dict[str, Any] = {
        "fitted_on": (
            f"calibration seeds {CALIBRATION_SEEDS[0]}-{CALIBRATION_SEEDS[-1]} (simulator output)"
        ),
        "pass_difficulty": {
            "features": ["length_m", "receiver_space_m", "lane_defenders", "under_pressure"],
            **pd_model,
        },
        "xg": {"features": ["distance_m", "angle_rad", "header"], **logistic_fit(sX, sy)},
        "xt": {"cols": XT_COLS, "rows": XT_ROWS, "grid": np.round(grid, 5).tolist()},
        "control": ref,
    }
    PARAMS_PATH.write_text(json.dumps(out, indent=2) + "\n")
    for k in ("pass_difficulty", "xg"):
        m = out[k]
        print(
            f"{k}: n={m['n']} base_rate={m['base_rate']:.3f} auc={m['auc']:.3f} "
            f"coef={np.round(m['coef'], 3)}"
        )
    print(f"difficult pass threshold: {pd_model['difficult_pass_threshold']:.3f}")
    print(f"xt: max={grid.max():.3f} at {np.unravel_index(grid.argmax(), grid.shape)}")
    print(
        "control refs:", {k: (round(v["median"], 3), round(v["scale"], 3)) for k, v in ref.items()}
    )
    if not math.isfinite(out["xg"]["auc"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
