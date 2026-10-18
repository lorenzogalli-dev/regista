"""Candidate moments from code (no model calls): the Detector's pre-filter.

Every `CHECK_MS` of match time, for each team (and each midfielder for `player_arc`), the signals
of each storyline type are measured over the last `WINDOW_MIN` minutes against everything before
that window. Nothing after the current time is read: windows end at `now`.

Each signal is scored with a robust z against noise measured the same way on matches without
scripted scenarios (`agents/detector_params.json`, fitted by `python -m eval.fit_detector` on public
data only). A candidate needs at least two signals above their own noise p95 (the D2.0 rule);
`wide`, which has a single signal, needs it above the noise p99.
"""

import json
import math
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from metrics import counters
from metrics.store import MatchStore
from sim.roster import LINE
from sim.schema import TICK_MS

PARAMS_PATH = Path(__file__).with_name("detector_params.json")
MIN_MS = 60_000
CHECK_MS = 60_000
MIN_BEFORE_MIN = 10

# (metric, subject role, expected direction) per candidate kind; roles: team, opp, player.
SIGNALS: dict[str, list[tuple[str, str, int]]] = {
    "pressing_spell": [
        ("ppda", "team", -1),
        ("pass_completion", "opp", -1),
        ("field_tilt", "team", 1),
    ],
    "momentum_shift": [("possession", "team", 1), ("field_tilt", "team", 1)],
    "tactical_switch/long_ball": [("avg_pass_length", "team", 1), ("pass_completion", "team", -1)],
    "tactical_switch/wide": [("width", "team", 1)],
    "player_arc": [("progressive_passes", "player", 1), ("touches", "player", 1)],
}
WINDOW_MIN = {
    "pressing_spell": 15,
    "momentum_shift": 15,
    "tactical_switch/long_ball": 16,
    "tactical_switch/wide": 16,
    "player_arc": 18,
}
PLAYER_KINDS = {"player_arc"}
PLAYER_FIELD = {"progressive_passes": "prog_passes", "touches": "touches"}


@dataclass(frozen=True)
class Signal:
    metric: str
    subject: str  # team_id or player_id
    direction: int
    window_value: float
    before_value: float
    z: float
    over_p95: bool


@dataclass
class Candidate:
    candidate_id: str
    kind: str
    t_ms: int
    team_id: str
    player_id: str | None
    window_start_ms: int
    window_end_ms: int
    signals: list[Signal]
    score: float  # mean signal z

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind,
            "t_ms": self.t_ms,
            "team_id": self.team_id,
            "player_id": self.player_id,
            "window_start_ms": self.window_start_ms,
            "window_end_ms": self.window_end_ms,
            "score": round(self.score, 2),
            "signals": [
                {
                    "metric": s.metric,
                    "subject": s.subject,
                    "expected": "up" if s.direction > 0 else "down",
                    "window": round(s.window_value, 3),
                    "before": round(s.before_value, 3),
                    "z": round(s.z, 2),
                    "above_noise_p95": s.over_p95,
                }
                for s in self.signals
            ],
        }


@cache
def params() -> dict[str, Any]:
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(f"{PARAMS_PATH} missing: run `uv run python -m eval.fit_detector`")
    data: dict[str, Any] = json.loads(PARAMS_PATH.read_text())
    return data


def _team_value(store: MatchStore, metric: str, team: str, start: int, end: int) -> float:
    teams, _ = store.counters(start, end)
    return counters.team_metrics(teams[team], teams[store.other(team)])[metric]


def _minutes_on(store: MatchStore, player: str, start: int, end: int) -> float:
    i0, i1 = start // TICK_MS, end // TICK_MS
    col = store.speed[i0:i1, store.player_index[player]]
    return float(np.count_nonzero(~np.isnan(col))) * TICK_MS / MIN_MS


def _player_value(store: MatchStore, metric: str, player: str, start: int, end: int) -> float:
    mins = _minutes_on(store, player, start, end)
    if mins <= 0:
        return math.nan
    _, players = store.counters(start, end)
    return players.get(player, {}).get(PLAYER_FIELD[metric], 0.0) / mins


def raw_effects(
    store: MatchStore, kind: str, team: str, player: str | None, start: int, end: int
) -> list[tuple[str, str, int, float, float]]:
    """(metric, subject, direction, window value, value before the window) per signal."""
    out = []
    for metric, role, direction in SIGNALS[kind]:
        if role == "player":
            assert player is not None
            subject = player
            w = _player_value(store, metric, player, start, end)
            b = _player_value(store, metric, player, 0, start)
        else:
            subject = team if role == "team" else store.other(team)
            w = _team_value(store, metric, subject, start, end)
            b = _team_value(store, metric, subject, 0, start)
        out.append((metric, subject, direction, w, b))
    return out


def subjects(store: MatchStore, kind: str, t: int) -> list[tuple[str, str | None]]:
    """(team, player) pairs to check at `t`: teams, or midfielders on the pitch for the whole
    window for player kinds."""
    if kind not in PLAYER_KINDS:
        return [(team, None) for team in store.team_ids]
    start = t - WINDOW_MIN[kind] * MIN_MS
    out: list[tuple[str, str | None]] = []
    for p in store.meta.players:
        if LINE[p.position] != "MID":
            continue
        if _minutes_on(store, p.player_id, start, t) >= WINDOW_MIN[kind] - 0.05:
            out.append((p.team_id, p.player_id))
    return out


def score(
    kind: str, effects: list[tuple[str, str, int, float, float]]
) -> tuple[list[Signal], bool] | None:
    """Robust z per signal and whether the candidate rule fires; None if a value is undefined."""
    ref = params()["kinds"][kind]
    sigs = []
    for (metric, subject, d, w, b), med, scale, p95 in zip(
        effects, ref["median"], ref["scale"], ref["p95"], strict=True
    ):
        if math.isnan(w) or math.isnan(b):
            return None
        z = (d * (w - b) - med) / scale
        sigs.append(Signal(metric, subject, d, w, b, z, z > p95))
    fires = sigs[0].z > ref["p99"][0] if len(sigs) == 1 else sum(s.over_p95 for s in sigs) >= 2
    return sigs, fires


@dataclass
class CandidateFinder:
    """Checks the live store every CHECK_MS of match time; one candidate per (kind, subject)
    per window length (cooldown)."""

    store: MatchStore
    next_check: int = MIN_BEFORE_MIN * MIN_MS
    cooldown: dict[tuple[str, str, str | None], int] = field(default_factory=dict)
    count: int = 0

    def poll(self) -> list[Candidate]:
        out: list[Candidate] = []
        now = self.store.now_ms
        while self.next_check <= now:
            out.extend(self.check(self.next_check))
            self.next_check += CHECK_MS
        return out

    def check(self, t: int) -> list[Candidate]:
        out = []
        for kind, minutes in WINDOW_MIN.items():
            start = t - minutes * MIN_MS
            if start < MIN_BEFORE_MIN * MIN_MS:
                continue
            for team, player in subjects(self.store, kind, t):
                key = (kind, team, player)
                if self.cooldown.get(key, -1) > t:
                    continue
                res = score(kind, raw_effects(self.store, kind, team, player, start, t))
                if res is None or not res[1]:
                    continue
                sigs = res[0]
                self.count += 1
                self.cooldown[key] = t + minutes * MIN_MS
                out.append(
                    Candidate(
                        candidate_id=f"c_{self.count:03d}",
                        kind=kind,
                        t_ms=t,
                        team_id=team,
                        player_id=player,
                        window_start_ms=start,
                        window_end_ms=t,
                        signals=sigs,
                        score=float(np.mean([s.z for s in sigs])),
                    )
                )
        return out
