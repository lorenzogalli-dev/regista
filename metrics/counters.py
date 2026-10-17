"""Per-event counters: the single definition of every event-based metric.

`contributions(event)` lists what one event adds to team and player counters. Minute bins
(offline analysis) and the live store (tools) both sum these, so a metric cannot drift
between the two. Metric formulas over the summed counters live in `metrics.bins`.
"""

from collections.abc import Callable
from typing import Any

import numpy as np

from sim.schema import PITCH_LENGTH, PITCH_WIDTH

FINAL_THIRD_X = 70.0
PPDA_ZONE_X = 0.6 * PITCH_LENGTH  # opponent's own 60 %
FLANK_LEFT_Y = PITCH_WIDTH * 2 / 3
FLANK_RIGHT_Y = PITCH_WIDTH / 3
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
    "shots",
)
PLAYER_FIELDS = ("touches", "prog_passes", "passes", "passes_complete")

# (scope, key, field, value); scope is "team" or "player", key a team_id or player_id
Contribution = tuple[str, str, str, float]
ToAttacking = Callable[[str, int, float, float], tuple[float, float]]


def is_progressive(sx: float, ex: float) -> bool:
    """Completed pass advancing >= 30 m within own half, >= 15 m across halfway, >= 10 m in
    the opponent half (attacking-frame x coordinates)."""
    half = PITCH_LENGTH / 2
    adv = ex - sx
    if sx < half and ex < half:
        return adv >= 30.0
    if sx < half <= ex:
        return adv >= 15.0
    return adv >= 10.0


def contributions(
    e: dict[str, Any], to_attacking: ToAttacking, other_team: Callable[[str], str]
) -> list[Contribution]:
    team = e["team_id"]
    if team is None:
        return []
    out: list[Contribution] = []
    per = e["period"]
    ax, ay = to_attacking(team, per, e["x"], e["y"])
    typ = e["type"]
    player = e["player_id"]
    if typ in TOUCH_TYPES:
        if ax >= FINAL_THIRD_X:
            out.append(("team", team, "f3_touches", 1.0))
            if ay >= FLANK_LEFT_Y:
                out.append(("team", team, "f3_left", 1.0))
            elif ay <= FLANK_RIGHT_Y:
                out.append(("team", team, "f3_right", 1.0))
        if player:
            out.append(("player", player, "touches", 1.0))
    if typ in ("pass", "carry"):
        out.append(("team", team, "width_sum", abs(e["y"] - PITCH_WIDTH / 2)))
        out.append(("team", team, "width_n", 1.0))
    if typ == "shot":
        out.append(("team", team, "shots", 1.0))
    if typ == "pass":
        out.append(("team", team, "passes", 1.0))
        length = float(np.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"]))
        out.append(("team", team, "pass_len_sum", length))
        if player:
            out.append(("player", player, "passes", 1.0))
        if ax < PPDA_ZONE_X:
            out.append(("team", other_team(team), "opp_passes_zone", 1.0))
        if e["outcome"] == "complete":
            out.append(("team", team, "passes_complete", 1.0))
            if player:
                out.append(("player", player, "passes_complete", 1.0))
            ex, _ = to_attacking(team, per, e["end_x"], e["end_y"])
            if player and is_progressive(ax, ex):
                out.append(("player", player, "prog_passes", 1.0))
            if e["recipient_id"]:
                out.append(("player", e["recipient_id"], "touches", 1.0))
    if typ in DEF_ACTIONS and ax > PITCH_LENGTH - PPDA_ZONE_X:
        out.append(("team", team, "def_actions_zone", 1.0))
    return out


def possession_ms(changes: list[tuple[int, str]], start: int, end: int) -> dict[str, float]:
    """Time-based possession: ms per team in [start, end) from (t_ms, team_id) changes
    (kickoff and possession_change events), each team holding until the next change."""
    out: dict[str, float] = {}
    for i, (t0, team) in enumerate(changes):
        t1 = changes[i + 1][0] if i + 1 < len(changes) else end
        lo, hi = max(t0, start), min(t1, end)
        if hi > lo:
            out[team] = out.get(team, 0.0) + (hi - lo)
    return out


def _ratio(num: float, den: float) -> float:
    return num / den if den > 0 else float("nan")


TEAM_METRICS = (
    "pass_completion",
    "avg_pass_length",
    "ppda",
    "field_tilt",
    "possession",
    "width",
    "flank_attack_share_left",
    "flank_attack_share_right",
)


def team_metrics(own: dict[str, float], other: dict[str, float]) -> dict[str, float]:
    """Window metrics from summed counters of the team (`own`) and its opponent (`other`).

    `possession` is time-based possession and needs a `poss_ms` entry in both dicts.
    """
    return {
        "pass_completion": _ratio(own["passes_complete"], own["passes"]),
        "avg_pass_length": _ratio(own["pass_len_sum"], own["passes"]),
        "ppda": _ratio(own["opp_passes_zone"], max(own["def_actions_zone"], 1.0)),
        "field_tilt": _ratio(own["f3_touches"], own["f3_touches"] + other["f3_touches"]),
        "possession": _ratio(
            own.get("poss_ms", 0.0), own.get("poss_ms", 0.0) + other.get("poss_ms", 0.0)
        ),
        "width": _ratio(own["width_sum"], own["width_n"]),
        "flank_attack_share_left": _ratio(own["f3_left"], own["f3_touches"]),
        "flank_attack_share_right": _ratio(own["f3_right"], own["f3_touches"]),
    }
