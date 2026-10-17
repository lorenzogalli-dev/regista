"""Tiny hand-built matches for metric unit tests."""

from typing import Any

import numpy as np

from metrics.data import MatchData
from sim import roster
from sim.rng import streams
from sim.schema import MatchMeta

P1_END = 3 * 60_000
P2_END = 6 * 60_000


def meta() -> MatchMeta:
    home, away, venue = roster.build(streams(1).roster)
    return MatchMeta(
        match_id="m_test",
        seed=1,
        competition="Synthetic League",
        venue=venue,
        home=home.team,
        away=away.team,
        players=home.players + away.players,
        period_end_ms=[P1_END, P2_END],
    )


def match(events: list[dict[str, Any]], speed: dict[str, np.ndarray] | None = None) -> MatchData:
    """Home starters stand in x < 52.5 in period 1 and x > 52.5 in period 2.

    So home attacks +x in the first half.
    """
    m = meta()
    ids = [p.player_id for p in m.players]
    T = P2_END // 100
    t = np.arange(T) * 100
    period = np.where(t < P1_END, 1, 2).astype(np.int8)
    pos = np.full((T, len(ids), 2), np.nan)
    spd = np.full((T, len(ids)), np.nan)
    for i, p in enumerate(m.players):
        if not p.starter:
            continue
        home = p.team_id == m.home.team_id
        x1 = 30.0 if home else 75.0
        pos[:, i, 0] = np.where(period == 1, x1, 105.0 - x1)
        pos[:, i, 1] = 34.0
        spd[:, i] = 2.0
    for pid, arr in (speed or {}).items():
        spd[:, ids.index(pid)] = arr
    full_events = [
        {
            "event_id": f"e_{i:06d}",
            "match_id": "m_test",
            "end_x": None,
            "end_y": None,
            "outcome": None,
            "recipient_id": None,
            "possession_id": 0,
            "qualifiers": {},
            "player_id": None,
            **e,
        }
        for i, e in enumerate(events)
    ]
    for e in full_events:
        e.setdefault("period", 1 if e["t_ms"] < P1_END else 2)
    return MatchData(
        meta=m,
        events=full_events,
        t_ms=t,
        period=period,
        ball=np.zeros((T, 4)),
        player_ids=ids,
        pos=pos,
        speed=spd,
    )
