"""Live match state built incrementally from the event and tracking stream.

`MatchStore` ingests events and frames as they arrive (in stream order) and answers
queries for any window up to the latest ingested time: queries never see the future.

Physical metrics from tracking:
- distance: sum of frame-to-frame displacements, skipping the first frame of each period
  (players are reset to kickoff positions at half time) and any step above 1.5 m in
  0.1 s (15 m/s, not humanly possible), which is treated as a data jump;
- high-intensity distance: the same, counting only steps above 5.5 m/s;
- sprints: runs above 7 m/s sustained for at least 1 s (0.5 s rolling-mean speed);
- top speed: maximum 0.5 s rolling-mean speed.

Threshold triggers (tier-0 overlays, no agent involved): player speed above 9 m/s (0.5 s
rolling mean, at most once per player per 5 minutes), shot speed above 30 m/s, a completed
pass whose difficulty is in the hardest 2 % of completed passes on calibration data
(SPEC suggested 0.8; difficulty is a probability of failure, so completed passes almost
never reach 0.8 and the threshold is taken from data instead).
"""

import bisect
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from metrics import control, counters, models
from metrics.bins import SMOOTH_FRAMES, SPRINT_MIN_FRAMES, SPRINT_MS
from sim.schema import PITCH_LENGTH, PITCH_WIDTH, TICK_MS, MatchMeta

MAX_STEP_M = 1.5
HI_SPEED_MS = 5.5
TRIGGER_SPEED_MS = 9.0
TRIGGER_SHOT_SPEED_MS = 30.0
TRIGGER_COOLDOWN_MS = {"speed": 300_000, "shot_speed": 0, "difficult_pass": 60_000}


@dataclass
class Trigger:
    t_ms: int
    kind: str  # speed | shot_speed | difficult_pass
    player_id: str
    team_id: str
    value: float
    unit: str
    event_id: str | None = None


@dataclass
class Enriched:
    """Derived values attached to one event at ingest time."""

    pass_length_m: float | None = None
    pass_progression_m: float | None = None
    pass_difficulty: float | None = None
    xg: float | None = None
    xt_added: float | None = None


@dataclass
class MatchStore:
    meta: MatchMeta
    events: list[dict[str, Any]] = field(default_factory=list)
    now_ms: int = -1

    def __post_init__(self) -> None:
        self.team_ids = (self.meta.home.team_id, self.meta.away.team_id)
        self.player_ids = [p.player_id for p in self.meta.players]
        self.player_index = {pid: i for i, pid in enumerate(self.player_ids)}
        self.player_team = {p.player_id: p.team_id for p in self.meta.players}
        n = self.meta.period_end_ms[-1] // TICK_MS + 1
        P = len(self.player_ids)
        self.pos = np.full((n, P, 2), np.nan, dtype=np.float32)
        self.speed = np.full((n, P), np.nan, dtype=np.float32)
        self.ball = np.full((n, 4), np.nan, dtype=np.float32)
        self.frame_period = np.zeros(n, dtype=np.int8)
        self.last_frame = -1
        self._dirs: dict[tuple[str, int], int] = {}
        self._pending: list[dict[str, Any]] = []
        self.event_t: list[int] = []
        self.contrib: list[list[counters.Contribution]] = []
        self.enriched: dict[str, Enriched] = {}
        self.changes: list[tuple[int, str]] = []
        self.score = {t: 0 for t in self.team_ids}
        self.triggers: list[Trigger] = []
        self._last_trigger: dict[tuple[str, str], int] = {}

    # ------------------------------------------------------------------ ingest

    def other(self, team: str) -> str:
        return self.team_ids[1 - self.team_ids.index(team)]

    def direction(self, team: str, period: int) -> int:
        return self._dirs[(team, period)]

    def to_attacking(self, team: str, period: int, x: float, y: float) -> tuple[float, float]:
        if self.direction(team, period) == 1:
            return x, y
        return PITCH_LENGTH - x, PITCH_WIDTH - y

    def ingest_frame(self, f: dict[str, Any]) -> None:
        i = f["t_ms"] // TICK_MS
        period = f["period"]
        b = f["ball"]
        self.ball[i] = (b["x"], b["y"], b["z"], b["speed_ms"])
        self.frame_period[i] = period
        for pl in f["players"]:
            k = self.player_index[pl["player_id"]]
            self.pos[i, k] = (pl["x"], pl["y"])
            self.speed[i, k] = pl["speed_ms"]
        self.last_frame = max(self.last_frame, i)
        self.now_ms = max(self.now_ms, f["t_ms"])
        if (self.team_ids[0], period) not in self._dirs:
            self._infer_direction(i, period)
            pending, self._pending = self._pending, []
            for e in pending:
                self._process_event(e)
        self._speed_triggers(i)

    def ingest_event(self, e: dict[str, Any]) -> None:
        self.now_ms = max(self.now_ms, e["t_ms"])
        if e["team_id"] is not None and (e["team_id"], e["period"]) not in self._dirs:
            self._pending.append(e)  # direction known at the period's first frame
            return
        self._process_event(e)

    def _infer_direction(self, i: int, period: int) -> None:
        for team in self.team_ids:
            cols = [k for k, pid in enumerate(self.player_ids) if self.player_team[pid] == team]
            mean_x = float(np.nanmean(self.pos[i, cols, 0]))
            self._dirs[(team, period)] = 1 if mean_x < PITCH_LENGTH / 2 else -1

    def _snapshot(self, t_ms: int) -> models.Snapshot:
        i = max(0, min(self.last_frame, t_ms // TICK_MS - 1))
        return models.Snapshot(self.pos[i], self.player_ids, self.player_team, self.player_index)

    def _process_event(self, e: dict[str, Any]) -> None:
        self.events.append(e)
        self.event_t.append(e["t_ms"])
        self.contrib.append(counters.contributions(e, self.to_attacking, self.other))
        typ, team = e["type"], e["team_id"]
        if typ in ("kickoff", "possession_change"):
            self.changes.append((e["t_ms"], team))
        if typ == "goal":
            self.score[team] += 1
        if typ in ("pass", "carry", "shot"):
            self._enrich(e)

    def _enrich(self, e: dict[str, Any]) -> None:
        team, per = e["team_id"], e["period"]
        ax, ay = self.to_attacking(team, per, e["x"], e["y"])
        en = Enriched()
        if e["type"] == "shot":
            head = e["qualifiers"].get("body_part") == "head"
            en.xg = models.xg(models.shot_features(ax, ay, head))
            speed = float(e["qualifiers"].get("ball_speed_ms", 0.0))
            if speed > TRIGGER_SHOT_SPEED_MS:
                self._fire(
                    "shot_speed", e["player_id"], team, speed, "m/s", e["t_ms"], e["event_id"]
                )
        else:
            ex, ey = self.to_attacking(team, per, e["end_x"], e["end_y"])
            ok = e["type"] == "carry" or e["outcome"] == "complete"
            if ok:
                en.xt_added = models.xt(ex, ey) - models.xt(ax, ay)
            if e["type"] == "pass":
                en.pass_length_m = float(np.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"]))
                en.pass_progression_m = ex - ax
                en.pass_difficulty = models.pass_difficulty(
                    models.pass_features(e, self._snapshot(e["t_ms"]))
                )
                if ok and en.pass_difficulty > models.difficult_pass_threshold():
                    self._fire(
                        "difficult_pass",
                        e["player_id"],
                        team,
                        en.pass_difficulty,
                        "",
                        e["t_ms"],
                        e["event_id"],
                    )
        self.enriched[e["event_id"]] = en

    def _fire(
        self, kind: str, pid: str, team: str, value: float, unit: str, t: int, eid: str | None
    ) -> None:
        last = self._last_trigger.get((kind, pid))
        if last is not None and t - last < TRIGGER_COOLDOWN_MS[kind]:
            return
        self._last_trigger[(kind, pid)] = t
        self.triggers.append(Trigger(t, kind, pid, team, round(value, 3), unit, eid))

    def _speed_triggers(self, i: int) -> None:
        if i < SMOOTH_FRAMES - 1:
            return
        win = self.speed[i - SMOOTH_FRAMES + 1 : i + 1]
        if np.isnan(win).any(axis=0).all():
            return
        with np.errstate(invalid="ignore"):
            smooth = win.mean(axis=0)
        for k in np.flatnonzero(smooth > TRIGGER_SPEED_MS):
            pid = self.player_ids[int(k)]
            self._fire(
                "speed", pid, self.player_team[pid], float(smooth[k]), "m/s", i * TICK_MS, None
            )

    # ------------------------------------------------------------------ queries

    def clamp(self, start: int, end: int) -> tuple[int, int]:
        """Restrict a window to what has been ingested: no query sees the future."""
        end = min(end, self.now_ms + 1)
        start = max(0, min(start, end))
        return start, end

    def events_between(self, start: int, end: int) -> list[dict[str, Any]]:
        start, end = self.clamp(start, end)
        lo = bisect.bisect_left(self.event_t, start)
        hi = bisect.bisect_left(self.event_t, end)
        return self.events[lo:hi]

    def counters(
        self, start: int, end: int
    ) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
        """Summed event counters per team (with time-based `poss_ms`) and per player."""
        start, end = self.clamp(start, end)
        teams = {t: dict.fromkeys((*counters.TEAM_FIELDS, "poss_ms"), 0.0) for t in self.team_ids}
        players: dict[str, dict[str, float]] = {}
        lo = bisect.bisect_left(self.event_t, start)
        hi = bisect.bisect_left(self.event_t, end)
        for contrib in self.contrib[lo:hi]:
            for scope, key, fld, val in contrib:
                if scope == "team":
                    teams[key][fld] += val
                else:
                    players.setdefault(key, dict.fromkeys(counters.PLAYER_FIELDS, 0.0))[fld] += val
        for team, ms in counters.possession_ms(self.changes, start, end).items():
            teams[team]["poss_ms"] = ms
        return teams, players

    def control_components(self, team: str, start: int, end: int) -> dict[str, float]:
        start, end = self.clamp(start, end)
        return control.components(
            self.events_between(start, end), self.changes, team, start, end, self.to_attacking
        )

    def physical(self, player_id: str, start: int, end: int) -> dict[str, float]:
        start, end = self.clamp(start, end)
        k = self.player_index[player_id]
        i0 = -(-start // TICK_MS)  # frames with start <= t < end
        i1 = max(i0, -(-end // TICK_MS))
        i1 = min(i1, self.last_frame + 1)
        pad = max(0, i0 - (SMOOTH_FRAMES - 1))
        sp = self.speed[pad:i1, k].astype(float)
        pos = self.pos[i0:i1, k].astype(float)
        per = self.frame_period[i0:i1]
        on = ~np.isnan(pos[:, 0])
        minutes = float(on.sum()) * TICK_MS / 60_000
        if len(pos) < 2 or not on.any():
            return {
                "distance_m": 0.0,
                "high_intensity_m": 0.0,
                "sprints": 0.0,
                "top_speed_ms": 0.0,
                "minutes_on_pitch": minutes,
            }
        step = np.hypot(*np.diff(pos, axis=0).T)
        valid = ~np.isnan(step) & (step <= MAX_STEP_M) & (per[1:] == per[:-1])
        dist = float(step[valid].sum())
        hi = float(step[valid & (step / (TICK_MS / 1000) > HI_SPEED_MS)].sum())
        cs = np.cumsum(np.concatenate([[0.0], np.nan_to_num(sp)]))
        cn = np.cumsum(np.concatenate([[0.0], (~np.isnan(sp)).astype(float)]))
        k_ = SMOOTH_FRAMES
        num, den = cs[k_:] - cs[:-k_], cn[k_:] - cn[:-k_]
        smooth = np.where(den == k_, num / np.maximum(den, 1), np.nan)
        offset = (i0 - pad) - (k_ - 1)  # align smoothed values with frames i0..i1
        sm = (
            smooth[max(0, offset) :]
            if offset >= 0
            else np.concatenate([np.full(-offset, np.nan), smooth])
        )
        above = np.nan_to_num(sm, nan=0.0) >= SPRINT_MS
        edges = np.flatnonzero(np.diff(np.concatenate([[0], above.astype(np.int8), [0]])))
        sprints = sum(
            1 for s, e in zip(edges[::2], edges[1::2], strict=True) if e - s >= SPRINT_MIN_FRAMES
        )
        top = float(np.nanmax(sm)) if not np.isnan(sm).all() else 0.0
        return {
            "distance_m": dist,
            "high_intensity_m": hi,
            "sprints": float(sprints),
            "top_speed_ms": top,
            "minutes_on_pitch": minutes,
        }

    def triggers_between(self, start: int, end: int) -> list[Trigger]:
        start, end = self.clamp(start, end)
        return [t for t in self.triggers if start <= t.t_ms < end]
