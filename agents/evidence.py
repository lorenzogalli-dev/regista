"""Evidence packs for the Analyst and the code half of the Verifier.

The pack holds metric values computed by the metrics tools for the moment's window and for the
window of the same length just before it. The Verifier recomputes every evidence item an
explanation cites by calling the same tool with the same arguments.
"""

import math
from collections.abc import Iterator
from typing import Any

from agents.candidates import Candidate
from agents.schemas import Evidence
from metrics.tools import MatchTools

TEAM_METRICS = (
    "possession_time_based",
    "field_tilt",
    "ppda",
    "pass_completion",
    "avg_pass_length_m",
    "width_m",
    "xt_added",
    "control_index",
)
PLAYER_METRICS = (
    "minutes_on_pitch",
    "touches",
    "progressive_passes",
    "passes",
    "sprints",
    "distance_m",
)
ABS_TOL = 0.0015
REL_TOL = 0.01


def windows(c: Candidate) -> tuple[tuple[int, int], tuple[int, int]]:
    """(before, after): the moment's window and the same length immediately before it (shorter
    early in a half; player counts then need their minutes on the pitch)."""
    length = c.window_end_ms - c.window_start_ms
    before = (max(0, c.window_start_ms - length), c.window_start_ms)
    return before, (c.window_start_ms, c.window_end_ms)


def _team_items(
    tools: MatchTools, team: str, before: tuple[int, int], after: tuple[int, int]
) -> Iterator[Evidence]:
    a = tools.get_window_stats(team, *before)
    b = tools.get_window_stats(team, *after)
    for m in TEAM_METRICS:
        va, vb = getattr(a, m), getattr(b, m)
        if va is None or vb is None:
            continue
        yield Evidence(
            tool="get_window_stats",
            subject=team,
            metric=m,
            before_start_ms=before[0],
            before_end_ms=before[1],
            after_start_ms=after[0],
            after_end_ms=after[1],
            before=va,
            after=vb,
        )


def _player_items(
    tools: MatchTools, pid: str, before: tuple[int, int], after: tuple[int, int]
) -> Iterator[Evidence]:
    a = tools.get_player_physical(pid, *before)
    b = tools.get_player_physical(pid, *after)
    for m in PLAYER_METRICS:
        yield Evidence(
            tool="get_player_physical",
            subject=pid,
            metric=m,
            before_start_ms=before[0],
            before_end_ms=before[1],
            after_start_ms=after[0],
            after_end_ms=after[1],
            before=float(getattr(a, m)),
            after=float(getattr(b, m)),
        )


def pack(tools: MatchTools, c: Candidate) -> list[Evidence]:
    before, after = windows(c)
    items = list(_team_items(tools, c.team_id, before, after))
    items += list(_team_items(tools, tools.store.other(c.team_id), before, after))
    if c.player_id:
        items += list(_player_items(tools, c.player_id, before, after))
    return items


def value(tools: MatchTools, ev: Evidence, which: str) -> float | None:
    """Recompute one side of an evidence item with the tool it names."""
    start, end = (
        (ev.before_start_ms, ev.before_end_ms)
        if which == "before"
        else (ev.after_start_ms, ev.after_end_ms)
    )
    if ev.tool == "get_window_stats":
        if ev.metric not in TEAM_METRICS:
            return None
        v: Any = getattr(tools.get_window_stats(ev.subject, start, end), ev.metric)
    else:
        if ev.metric not in PLAYER_METRICS:
            return None
        v = getattr(tools.get_player_physical(ev.subject, start, end), ev.metric)
    return None if v is None else float(v)


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def recompute(tools: MatchTools, ev: Evidence) -> str | None:
    """None if the item matches the tool output, otherwise the reason it does not."""
    try:
        for which, claimed in (("before", ev.before), ("after", ev.after)):
            actual = value(tools, ev, which)
            if actual is None:
                return f"{ev.metric} for {ev.subject} is not a recomputable metric"
            if not close(actual, claimed):
                return (
                    f"{ev.metric} {which} for {ev.subject}: claimed {claimed}, tool says {actual}"
                )
    except ValueError as e:
        return str(e)
    return None
