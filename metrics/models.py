"""Fitted models: pass difficulty, xG, xT, and the control index.

All parameters are fitted by `python -m metrics.fit` on calibration seeds 2000-2199 and
stored in `metrics/params.json`. They are calibrated on the simulator, not on real
football, and are reported as such.

- Pass difficulty (0-1): estimated probability that a pass is not completed. Logistic
  regression on pass length, the intended receiver's nearest-opponent distance, the number
  of opponents within 2 m of the passing lane and the `under_pressure` flag, all read from
  the tracking frame just before the pass.
- xG: logistic regression on shot distance, goal-mouth angle and header flag.
- xT: expected threat on a 12 x 8 attacking-frame grid, by value iteration over pass,
  carry and shot frequencies (Karun Singh's formulation, fitted from scratch here).
- Control index (0-100, heuristic): mean of four sub-scores over a window: the team's
  mean possession length, turnovers per minute (fewer = more control), variability of the
  event rate (steadier = more control) and the share of the team's possessions that end in
  the opponent half. Each sub-score maps a value through a logistic centred on the
  calibration median, scaled by the calibration spread.
"""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from sim.pitch import goal_distance_angle
from sim.schema import PITCH_LENGTH, PITCH_WIDTH

PARAMS_PATH = Path(__file__).with_name("params.json")
XT_COLS, XT_ROWS = 12, 8
LANE_RADIUS_M = 2.0
PRESSURE_CAP_M = 10.0


@dataclass(frozen=True)
class Snapshot:
    """Player positions at one tracking frame."""

    pos: np.ndarray  # (P, 2), NaN when off the pitch
    player_ids: list[str]
    player_team: dict[str, str]
    index: dict[str, int]


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _opponents(snap: Snapshot, team: str) -> np.ndarray:
    rows = [i for i, p in enumerate(snap.player_ids) if snap.player_team[p] != team]
    pts = snap.pos[rows]
    return np.asarray(pts[~np.isnan(pts).any(axis=1)])


def lane_defenders(a: np.ndarray, b: np.ndarray, opp: np.ndarray) -> int:
    ab = b - a
    L2 = float(ab @ ab) or 1e-6
    t = np.clip(((opp - a) @ ab) / L2, 0.0, 1.0)
    d = np.hypot(*(opp - (a + t[:, None] * ab)).T)
    return int(np.sum(d < LANE_RADIUS_M))


def pass_features(e: dict[str, Any], snap: Snapshot) -> np.ndarray:
    """[length, receiver_space, lane_defenders, under_pressure]."""
    a = np.array([e["x"], e["y"]])
    b = np.array([e["end_x"], e["end_y"]])
    length = float(np.hypot(*(b - a)))
    opp = _opponents(snap, e["team_id"])
    space = PRESSURE_CAP_M
    rid = e.get("recipient_id")
    if rid and rid in snap.index:
        rp = snap.pos[snap.index[rid]]
        if not np.isnan(rp).any() and len(opp):
            space = min(PRESSURE_CAP_M, float(np.min(np.hypot(*(opp - rp).T))))
    lane = lane_defenders(a, b, opp) if len(opp) else 0
    up = 1.0 if e.get("qualifiers", {}).get("under_pressure") else 0.0
    return np.array([length, space, float(lane), up])


def shot_features(ax: float, ay: float, head: bool) -> np.ndarray:
    dist, angle = goal_distance_angle(ax, ay)
    return np.array([dist, angle, 1.0 if head else 0.0])


@cache
def params() -> dict[str, Any]:
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(f"{PARAMS_PATH} missing: run `uv run python -m metrics.fit`")
    data: dict[str, Any] = json.loads(PARAMS_PATH.read_text())
    return data


def _logit(model: dict[str, Any], x: np.ndarray) -> float:
    w = np.array(model["coef"])
    mu, sd = np.array(model["mean"]), np.array(model["std"])
    return float(model["intercept"] + ((x - mu) / sd) @ w)


def pass_difficulty(features: np.ndarray) -> float:
    return _sigmoid(_logit(params()["pass_difficulty"], features))


def difficult_pass_threshold() -> float:
    """Difficulty above which a completed pass is a highlight (top 2 % on calibration)."""
    return float(params()["pass_difficulty"]["difficult_pass_threshold"])


def xg(features: np.ndarray) -> float:
    return _sigmoid(_logit(params()["xg"], features))


def xt_zone(ax: float, ay: float) -> tuple[int, int]:
    c = min(XT_COLS - 1, max(0, int(ax / PITCH_LENGTH * XT_COLS)))
    r = min(XT_ROWS - 1, max(0, int(ay / PITCH_WIDTH * XT_ROWS)))
    return c, r


def xt(ax: float, ay: float) -> float:
    c, r = xt_zone(ax, ay)
    return float(params()["xt"]["grid"][c][r])


def control_index(components: dict[str, float]) -> float | None:
    """0-100 from the four components; None if any component is undefined."""
    ref = params()["control"]
    scores = []
    for name, sign in (
        ("possession_length_s", 1),
        ("turnovers_per_min", -1),
        ("event_rate_cv", -1),
        ("end_in_opp_half_share", 1),
    ):
        v = components.get(name)
        if v is None or math.isnan(v):
            return None
        r = ref[name]
        scores.append(_sigmoid(sign * (v - r["median"]) / r["scale"]))
    return 100.0 * float(np.mean(scores))
