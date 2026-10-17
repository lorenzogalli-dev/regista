"""Components of the control index over a time window (see metrics.models.control_index)."""

import itertools
from collections.abc import Callable
from typing import Any

import numpy as np

from sim.schema import PITCH_LENGTH

ON_BALL = {"pass", "carry", "shot", "tackle", "interception", "clearance", "ball_recovery", "save"}
BUCKET_MS = 30_000

ToAttacking = Callable[[str, int, float, float], tuple[float, float]]


def segments(changes: list[tuple[int, str]], end_ms: int) -> list[tuple[int, int, str]]:
    """Possession segments (start, end, team) from kickoff/possession_change times."""
    out = []
    for i, (t0, team) in enumerate(changes):
        t1 = changes[i + 1][0] if i + 1 < len(changes) else end_ms
        if t1 > t0:
            out.append((t0, t1, team))
    return out


def components(
    events: list[dict[str, Any]],
    changes: list[tuple[int, str]],
    team: str,
    start: int,
    end: int,
    to_attacking: ToAttacking,
) -> dict[str, float]:
    """`events` must be the match's events sorted by time (only [start, end) is used)."""
    segs = [s for s in segments(changes, end) if s[1] > start and s[0] < end]
    mine = [s for s in segs if s[2] == team]
    minutes = max((end - start) / 60_000, 1e-9)
    lengths = [(min(e, end) - max(s, start)) / 1000 for s, e, _ in mine]
    switches = sum(1 for (_, _, a), (_, _, b) in itertools.pairwise(segs) if a != b)

    window = [e for e in events if start <= e["t_ms"] < end and e["type"] in ON_BALL]
    n_buckets = max(1, (end - start) // BUCKET_MS)
    counts = np.zeros(n_buckets)
    for e in window:
        counts[min(n_buckets - 1, (e["t_ms"] - start) // BUCKET_MS)] += 1
    cv = float(counts.std() / counts.mean()) if counts.mean() > 0 else float("nan")

    ended = 0
    in_opp_half = 0
    for s, e_ms, _ in mine:
        if not (start <= e_ms <= end) or e_ms >= end:
            continue
        last = [ev for ev in window if s <= ev["t_ms"] < e_ms and ev["team_id"] == team]
        if not last:
            continue
        ev = last[-1]
        ax, _ = to_attacking(team, ev["period"], ev["x"], ev["y"])
        ended += 1
        in_opp_half += ax > PITCH_LENGTH / 2
    return {
        "possession_length_s": float(np.mean(lengths)) if lengths else float("nan"),
        "turnovers_per_min": switches / minutes,
        "event_rate_cv": cv,
        "end_in_opp_half_share": in_opp_half / ended if ended else float("nan"),
    }
