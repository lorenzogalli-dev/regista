"""Per-minute aggregates for teams and players, and window metrics computed from them.

Every metric over a time window is a ratio or rate of sums over one-minute bins, so a
window, its complement and sliding windows are all cheap to evaluate. Definitions:

- pass_completion: completed passes / passes.
- avg_pass_length: mean pass length (m), start to end location.
- ppda: opponent passes in their own 60 % of the pitch / our defensive actions (tackles,
  interceptions, fouls) in the same zone. Lower = more intense press.
- field_tilt: our final-third touches / both teams' final-third touches. Touches are
  passes, carries and shots; the final third starts 70 m from the team's own goal line.
- possession (time-based possession): share of match time in which the team was the
  possessing team, from kickoff and possession_change events. Dead-ball time counts for
  the team awarded the restart.
- width: mean distance (m) of our pass and carry start locations from the pitch's long axis.
- flank_attack_share_{left,right}: share of our final-third touches in the left/right
  outer third of the pitch, in our attacking direction.
- touches (per minute on pitch): passes, carries, shots and pass receptions.
- progressive_passes (per minute on pitch): completed passes that advance the ball at
  least 30 m (both ends in own half), 15 m (crossing halfway) or 10 m (both in the
  opponent half).
- top_speed: maximum 0.5 s rolling-mean speed (m/s).
- sprint_count (per minute on pitch): runs above 7 m/s sustained for at least 1 s.
"""

from dataclasses import dataclass, field

import numpy as np

from metrics import counters as C
from metrics.data import MIN_MS, MatchData
from sim.schema import TICK_MS

SPRINT_MS = 7.0
SPRINT_MIN_FRAMES = 1000 // TICK_MS
SMOOTH_FRAMES = 500 // TICK_MS
FRAMES_PER_MIN = MIN_MS // TICK_MS
TEAM_FIELDS = (*C.TEAM_FIELDS, "poss_ms")
PLAYER_FIELDS = ("touches", "prog_passes", "top_speed", "sprints", "on_frames")


@dataclass
class MinuteBins:
    team_ids: tuple[str, str]
    player_ids: list[str]
    n_minutes: int
    team: dict[str, np.ndarray] = field(default_factory=dict)  # field -> (2, n)
    player: dict[str, np.ndarray] = field(default_factory=dict)  # field -> (P, n)

    def team_idx(self, team_id: str) -> int:
        return self.team_ids.index(team_id)

    def player_idx(self, player_id: str) -> int:
        return self.player_ids.index(player_id)


is_progressive = C.is_progressive


def build(md: MatchData) -> MinuteBins:
    n = md.n_minutes
    P = len(md.player_ids)
    b = MinuteBins(md.team_ids, md.player_ids, n)
    b.team = {f: np.zeros((2, n)) for f in TEAM_FIELDS}
    b.player = {f: np.zeros((P, n)) for f in PLAYER_FIELDS}
    _events(md, b)
    _possession(md, b)
    _tracking(md, b)
    return b


def _events(md: MatchData, b: MinuteBins) -> None:
    team_idx = {t: i for i, t in enumerate(b.team_ids)}

    def other(team: str) -> str:
        return b.team_ids[1 - team_idx[team]]

    for e in md.events:
        m = min(e["t_ms"] // MIN_MS, b.n_minutes - 1)
        for scope, key, fld, val in C.contributions(e, md.to_attacking, other):
            if scope == "team":
                b.team[fld][team_idx[key], m] += val
            elif fld in b.player:
                b.player[fld][md.player_index[key], m] += val


def _possession(md: MatchData, b: MinuteBins) -> None:
    """Time-based possession per minute (see metrics.counters.possession_ms)."""
    changes = [
        (e["t_ms"], e["team_id"])
        for e in md.events
        if e["type"] in ("kickoff", "possession_change")
    ]
    for m in range(b.n_minutes):
        lo, hi = m * MIN_MS, min((m + 1) * MIN_MS, md.duration_ms)
        for team, ms in C.possession_ms(changes, lo, hi).items():
            b.team["poss_ms"][b.team_idx(team), m] += ms


def smoothed_speed(speed: np.ndarray) -> np.ndarray:
    """0.5 s trailing rolling mean along time; NaN stays NaN."""
    filled = np.nan_to_num(speed, nan=0.0)
    present = (~np.isnan(speed)).astype(float)
    k = SMOOTH_FRAMES
    cs = np.cumsum(np.vstack([np.zeros((1, speed.shape[1])), filled]), axis=0)
    cn = np.cumsum(np.vstack([np.zeros((1, speed.shape[1])), present]), axis=0)
    num = cs[k:] - cs[:-k]
    den = cn[k:] - cn[:-k]
    out = np.full_like(speed, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[k - 1 :] = np.where(den == k, num / den, np.nan)
    return out


def sprint_starts(smooth: np.ndarray) -> np.ndarray:
    """Boolean (T, P): frame where a sprint (>= SPRINT_MS for >= 1 s) begins."""
    above = np.nan_to_num(smooth, nan=0.0) >= SPRINT_MS
    starts = np.zeros_like(above)
    T = above.shape[0]
    for p in range(above.shape[1]):
        col = above[:, p]
        edges = np.flatnonzero(np.diff(np.concatenate([[0], col.astype(np.int8), [0]])))
        for s, e in zip(edges[::2], edges[1::2], strict=True):
            if e - s >= SPRINT_MIN_FRAMES and s < T:
                starts[s, p] = True
    return np.asarray(starts)


def _tracking(md: MatchData, b: MinuteBins) -> None:
    minute = np.minimum(md.t_ms // MIN_MS, b.n_minutes - 1)
    smooth = smoothed_speed(md.speed)
    starts = sprint_starts(smooth)
    on = ~np.isnan(md.speed)
    for m in range(b.n_minutes):
        rows = minute == m
        if not rows.any():
            continue
        b.player["on_frames"][:, m] = on[rows].sum(axis=0)
        b.player["sprints"][:, m] = starts[rows].sum(axis=0)
        sm = smooth[rows]
        with np.errstate(all="ignore"):
            b.player["top_speed"][:, m] = np.where(
                np.isnan(sm).all(axis=0), 0.0, np.nanmax(np.nan_to_num(sm, nan=-1.0), axis=0)
            )


# --------------------------------------------------------------------------- window metrics


def _ratio(num: float, den: float) -> float:
    return num / den if den > 0 else float("nan")


def team_metric(b: MinuteBins, metric: str, team_id: str, mask: np.ndarray) -> float:
    """Metric for `team_id` over the minutes selected by boolean `mask`."""
    ti = b.team_idx(team_id)
    own = {k: float(v[ti, mask].sum()) for k, v in b.team.items()}
    other = {k: float(v[1 - ti, mask].sum()) for k, v in b.team.items()}
    return C.team_metrics(own, other)[metric]


def player_metric(b: MinuteBins, metric: str, player_id: str, mask: np.ndarray) -> float:
    pi = b.player_idx(player_id)
    on_min = float(b.player["on_frames"][pi, mask].sum()) / FRAMES_PER_MIN
    if metric == "top_speed":
        vals = b.player["top_speed"][pi, mask]
        return float(vals.max()) if vals.size else float("nan")
    count = {"touches": "touches", "progressive_passes": "prog_passes", "sprint_count": "sprints"}
    if metric in count:
        return _ratio(float(b.player[count[metric]][pi, mask].sum()), on_min)
    raise KeyError(metric)


def full_minutes(b: MinuteBins, player_id: str) -> np.ndarray:
    """Minutes in which the player was on the pitch for the whole minute."""
    return np.asarray(b.player["on_frames"][b.player_idx(player_id)] >= FRAMES_PER_MIN)
