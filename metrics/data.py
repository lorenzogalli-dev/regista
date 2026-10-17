"""Public match data as the metrics engine sees it: metadata, events and tracking arrays.

The engine only uses what a real data feed would provide (match.json, events, tracking).
Attacking directions are inferred from tracking, not taken from simulator internals.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from sim import io
from sim.engine import SimResult
from sim.schema import PITCH_LENGTH, PITCH_WIDTH, MatchMeta

MIN_MS = 60_000


@dataclass
class MatchData:
    meta: MatchMeta
    events: list[dict[str, Any]]
    t_ms: np.ndarray  # (T,)
    period: np.ndarray  # (T,)
    ball: np.ndarray  # (T, 4) x, y, z, speed
    player_ids: list[str]
    pos: np.ndarray  # (T, P, 2), NaN when the player is not on the pitch
    speed: np.ndarray  # (T, P), NaN when not on the pitch

    def __post_init__(self) -> None:
        self.team_ids = (self.meta.home.team_id, self.meta.away.team_id)
        self.player_team = {p.player_id: p.team_id for p in self.meta.players}
        self.player_index = {pid: i for i, pid in enumerate(self.player_ids)}
        self._dirs = self._infer_directions()

    @property
    def duration_ms(self) -> int:
        return self.meta.period_end_ms[-1]

    @property
    def n_minutes(self) -> int:
        return -(-self.duration_ms // MIN_MS)

    def period_at(self, t_ms: int) -> int:
        return 1 if t_ms < self.meta.period_end_ms[0] else 2

    def direction(self, team_id: str, period: int) -> int:
        """+1 if `team_id` attacks towards x = 105 in `period`, else -1."""
        return self._dirs[(team_id, period)]

    def to_attacking(self, team_id: str, period: int, x: float, y: float) -> tuple[float, float]:
        if self.direction(team_id, period) == 1:
            return x, y
        return PITCH_LENGTH - x, PITCH_WIDTH - y

    def _infer_directions(self) -> dict[tuple[str, int], int]:
        """A team defends the goal its players stand closest to at the first frame of a period."""
        dirs: dict[tuple[str, int], int] = {}
        for period in (1, 2):
            idx = int(np.argmax(self.period == period))
            for team in self.team_ids:
                cols = [i for i, pid in enumerate(self.player_ids) if self.player_team[pid] == team]
                xs = self.pos[idx, cols, 0]
                mean_x = float(np.nanmean(xs))
                dirs[(team, period)] = 1 if mean_x < PITCH_LENGTH / 2 else -1
        return dirs


def from_sim(result: SimResult) -> MatchData:
    """Build from an in-memory simulation (same content as the written files, no I/O)."""
    meta = result.meta
    ids = [p.player_id for p in meta.players]
    T, P = len(result.t_ms), len(ids)
    pos = np.full((T, P, 2), np.nan)
    speed = np.full((T, P), np.nan)
    rows = np.arange(T)
    for slot in range(result.slot_player.shape[1]):
        k = result.slot_player[:, slot]
        on = k >= 0
        pos[rows[on], k[on]] = np.round(result.pos[on, slot], 2)
        speed[rows[on], k[on]] = np.round(result.speed[on, slot], 2)
    return MatchData(
        meta=meta,
        events=result.events,
        t_ms=result.t_ms,
        period=result.period,
        ball=np.round(result.ball, 2),
        player_ids=ids,
        pos=pos,
        speed=speed,
    )


def from_dir(match_dir: Path) -> MatchData:
    meta = io.read_meta(match_dir)
    events = list(io.iter_events(match_dir))
    return from_frames(meta, events, io.iter_tracking(match_dir))


def from_frames(
    meta: MatchMeta, events: list[dict[str, Any]], frames: Iterable[dict[str, Any]]
) -> MatchData:
    ids = [p.player_id for p in meta.players]
    index = {pid: i for i, pid in enumerate(ids)}
    t, per, ball, pos_rows, spd_rows = [], [], [], [], []
    for f in frames:
        t.append(f["t_ms"])
        per.append(f["period"])
        b = f["ball"]
        ball.append((b["x"], b["y"], b["z"], b["speed_ms"]))
        p = np.full((len(ids), 2), np.nan)
        s = np.full(len(ids), np.nan)
        for pl in f["players"]:
            i = index[pl["player_id"]]
            p[i] = (pl["x"], pl["y"])
            s[i] = pl["speed_ms"]
        pos_rows.append(p)
        spd_rows.append(s)
    return MatchData(
        meta=meta,
        events=events,
        t_ms=np.array(t, dtype=np.int64),
        period=np.array(per, dtype=np.int8),
        ball=np.array(ball),
        player_ids=ids,
        pos=np.array(pos_rows),
        speed=np.array(spd_rows),
    )
