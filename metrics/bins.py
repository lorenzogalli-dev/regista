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

import itertools
from dataclasses import dataclass, field

import numpy as np

from metrics.data import MIN_MS, MatchData
from sim.schema import PITCH_LENGTH, PITCH_WIDTH, TICK_MS

FINAL_THIRD_X = 70.0
PPDA_ZONE_X = 0.6 * PITCH_LENGTH  # opponent's own 60 %
FLANK_LEFT_Y = PITCH_WIDTH * 2 / 3
FLANK_RIGHT_Y = PITCH_WIDTH / 3
SPRINT_MS = 7.0
SPRINT_MIN_FRAMES = 1000 // TICK_MS
SMOOTH_FRAMES = 500 // TICK_MS
FRAMES_PER_MIN = MIN_MS // TICK_MS
DEF_ACTIONS = {"tackle", "interception", "foul"}
TOUCH_TYPES = {"pass", "carry", "shot"}

TEAM_FIELDS = (
    "passes",
    "passes_complete",
    "pass_len_sum",
    "opp_passes_zone",
    "def_actions_zone",
    "f3_touches",
    "width_sum",
    "width_n",
    "f3_left",
    "f3_right",
    "poss_ms",
)
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


def is_progressive(sx: float, ex: float) -> bool:
    """Progressive pass rule on attacking-frame x coordinates (see module docstring)."""
    half = PITCH_LENGTH / 2
    adv = ex - sx
    if sx < half and ex < half:
        return adv >= 30.0
    if sx < half <= ex:
        return adv >= 15.0
    return adv >= 10.0


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
    T, Pl = b.team, b.player
    for e in md.events:
        team = e["team_id"]
        if team is None:
            continue
        ti = b.team_idx(team)
        m = min(e["t_ms"] // MIN_MS, b.n_minutes - 1)
        per = e["period"]
        ax, ay = md.to_attacking(team, per, e["x"], e["y"])
        typ = e["type"]
        pi = md.player_index.get(e["player_id"] or "")
        if typ in TOUCH_TYPES:
            if ax >= FINAL_THIRD_X:
                T["f3_touches"][ti, m] += 1
                if ay >= FLANK_LEFT_Y:
                    T["f3_left"][ti, m] += 1
                elif ay <= FLANK_RIGHT_Y:
                    T["f3_right"][ti, m] += 1
            if pi is not None:
                Pl["touches"][pi, m] += 1
        if typ in ("pass", "carry"):
            T["width_sum"][ti, m] += abs(e["y"] - PITCH_WIDTH / 2)
            T["width_n"][ti, m] += 1
        if typ == "pass":
            T["passes"][ti, m] += 1
            T["pass_len_sum"][ti, m] += float(np.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"]))
            if ax < PPDA_ZONE_X:
                T["opp_passes_zone"][1 - ti, m] += 1
            if e["outcome"] == "complete":
                T["passes_complete"][ti, m] += 1
                ex, _ = md.to_attacking(team, per, e["end_x"], e["end_y"])
                if pi is not None and is_progressive(ax, ex):
                    Pl["prog_passes"][pi, m] += 1
                ri = md.player_index.get(e["recipient_id"] or "")
                if ri is not None:
                    Pl["touches"][ri, m] += 1
        if typ in DEF_ACTIONS and ax > PITCH_LENGTH - PPDA_ZONE_X:
            T["def_actions_zone"][ti, m] += 1


def _possession(md: MatchData, b: MinuteBins) -> None:
    """Time-based possession: segments between kickoff / possession_change events."""
    changes = [
        (e["t_ms"], e["team_id"])
        for e in md.events
        if e["type"] in ("kickoff", "possession_change")
    ]
    changes.append((md.duration_ms, None))
    for (t0, team), (t1, _) in itertools.pairwise(changes):
        if team is None or t1 <= t0:
            continue
        ti = b.team_idx(team)
        m0, m1 = t0 // MIN_MS, (t1 - 1) // MIN_MS
        for m in range(m0, min(m1, b.n_minutes - 1) + 1):
            lo, hi = max(t0, m * MIN_MS), min(t1, (m + 1) * MIN_MS)
            b.team["poss_ms"][ti, m] += hi - lo


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
    T = {k: float(v[ti, mask].sum()) for k, v in b.team.items()}
    if metric == "pass_completion":
        return _ratio(T["passes_complete"], T["passes"])
    if metric == "avg_pass_length":
        return _ratio(T["pass_len_sum"], T["passes"])
    if metric == "ppda":
        return _ratio(T["opp_passes_zone"], max(T["def_actions_zone"], 1.0))
    if metric == "field_tilt":
        other = float(b.team["f3_touches"][1 - ti, mask].sum())
        return _ratio(T["f3_touches"], T["f3_touches"] + other)
    if metric == "possession":
        other = float(b.team["poss_ms"][1 - ti, mask].sum())
        return _ratio(T["poss_ms"], T["poss_ms"] + other)
    if metric == "width":
        return _ratio(T["width_sum"], T["width_n"])
    if metric == "flank_attack_share_left":
        return _ratio(T["f3_left"], T["f3_touches"])
    if metric == "flank_attack_share_right":
        return _ratio(T["f3_right"], T["f3_touches"])
    raise KeyError(metric)


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
