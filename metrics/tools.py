"""Typed tools over a live `MatchStore`: the only way agents get numbers.

Every tool answers from data ingested so far (never the future). Inputs are ids and
times only; no tool takes a path or reads files. Possession is always time-based
possession and is labelled `possession_time_based`.
"""

import math
from typing import Annotated, Any

from pydantic import BaseModel, Field

from metrics import counters, models
from metrics.store import MatchStore

TeamId = Annotated[str, Field(pattern=r"^t_[a-z]{3}$", description="team id, e.g. t_hrb")]
PlayerId = Annotated[
    str, Field(pattern=r"^p_[a-z]{3}_\d{2}$", description="player id, e.g. p_hrb_07")
]
Ms = Annotated[int, Field(ge=0, le=10_000_000, description="match time in ms since kickoff")]

MIN_MS = 60_000


def _num(x: float | None, nd: int = 3) -> float | None:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), nd)


class TeamInfo(BaseModel):
    team_id: str
    name: str
    short: str
    formation: str


class PlayerInfo(BaseModel):
    player_id: str
    team_id: str
    name: str
    shirt: int
    position: str
    starter: bool


class MatchInfo(BaseModel):
    match_id: str
    competition: str
    venue: str
    home: TeamInfo
    away: TeamInfo
    players: list[PlayerInfo]
    now_ms: int
    note: str = "All clubs, players and data are synthetic."


class WindowStats(BaseModel):
    team_id: str
    start_ms: int
    end_ms: int
    minutes: float
    possession_time_based: float | None = Field(description="share of time in possession (0-1)")
    field_tilt: float | None = Field(description="share of both teams' final-third touches (0-1)")
    ppda: float | None = Field(description="opponent passes per defensive action in their 60%")
    pass_completion: float | None
    passes: int
    avg_pass_length_m: float | None
    width_m: float | None
    flank_share_left: float | None
    flank_share_right: float | None
    shots: int
    goals: int
    xg: float = Field(description="sum of shot xG (model calibrated on synthetic data)")
    xt_added: float = Field(description="xT gained by completed passes and carries")
    control_index: float | None = Field(description="0-100 heuristic, see metrics.models")


class MetricDelta(BaseModel):
    metric: str
    before: float | None
    after: float | None
    delta: float | None


class WindowComparison(BaseModel):
    team_id: str
    before: tuple[int, int]
    after: tuple[int, int]
    deltas: list[MetricDelta]


class PlayerPhysical(BaseModel):
    player_id: str
    start_ms: int
    end_ms: int
    minutes_on_pitch: float
    distance_m: float
    high_intensity_m: float = Field(description="distance above 5.5 m/s")
    sprints: int = Field(description="runs above 7 m/s for at least 1 s")
    top_speed_ms: float = Field(description="max 0.5 s rolling-mean speed")
    top_speed_kmh: float
    touches: int
    passes: int
    passes_complete: int
    progressive_passes: int


class SequenceEvent(BaseModel):
    event_id: str
    t_ms: int
    type: str
    player_id: str | None
    outcome: str | None
    x: float
    y: float
    end_x: float | None
    end_y: float | None
    pass_length_m: float | None = None
    pass_progression_m: float | None = None
    pass_difficulty: float | None = None
    xg: float | None = None
    xt_added: float | None = None
    ball_speed_ms: float | None = None


class Sequence(BaseModel):
    possession_id: int
    team_id: str | None
    start_ms: int | None
    end_ms: int | None
    events: list[SequenceEvent]


class TriggerOut(BaseModel):
    t_ms: int
    kind: str
    player_id: str
    team_id: str
    value: float
    unit: str
    event_id: str | None


class MomentContext(BaseModel):
    t_ms: int
    clock: str
    period: int
    score: dict[str, int]
    recent_events: list[SequenceEvent]
    recent_triggers: list[TriggerOut]
    last_5_min: dict[str, WindowStats]
    last_15_min: dict[str, WindowStats]


class MatchTools:
    """Tool implementations bound to one match store."""

    def __init__(self, store: MatchStore) -> None:
        self.store = store

    def _team(self, team_id: str) -> str:
        if team_id not in self.store.team_ids:
            raise ValueError(f"unknown team {team_id}")
        return team_id

    def _player(self, player_id: str) -> str:
        if player_id not in self.store.player_index:
            raise ValueError(f"unknown player {player_id}")
        return player_id

    def clock(self, t_ms: int) -> tuple[str, int]:
        p1 = self.store.meta.period_end_ms[0]
        if t_ms < p1:
            s, period = t_ms // 1000, 1
        else:
            s, period = 45 * 60 + (t_ms - p1) // 1000, 2
        return f"{s // 60:02d}:{s % 60:02d}", period

    def get_match_info(self) -> MatchInfo:
        m = self.store.meta

        def team(t: object) -> TeamInfo:
            return TeamInfo.model_validate(t, from_attributes=True)

        return MatchInfo(
            match_id=m.match_id,
            competition=m.competition,
            venue=m.venue,
            home=team(m.home),
            away=team(m.away),
            players=[PlayerInfo.model_validate(p, from_attributes=True) for p in m.players],
            now_ms=max(0, self.store.now_ms),
        )

    def get_window_stats(self, team_id: str, start_ms: int, end_ms: int) -> WindowStats:
        team = self._team(team_id)
        st = self.store
        start, end = st.clamp(start_ms, end_ms)
        teams, _ = st.counters(start, end)
        own, other = teams[team], teams[st.other(team)]
        m = counters.team_metrics(own, other)
        evs = st.events_between(start, end)
        xg = sum(
            (st.enriched[e["event_id"]].xg or 0.0)
            for e in evs
            if e["type"] == "shot" and e["team_id"] == team
        )
        xt = sum(
            (st.enriched[e["event_id"]].xt_added or 0.0)
            for e in evs
            if e["type"] in ("pass", "carry") and e["team_id"] == team
        )
        goals = sum(1 for e in evs if e["type"] == "goal" and e["team_id"] == team)
        ctrl = (
            models.control_index(st.control_components(team, start, end)) if end > start else None
        )
        return WindowStats(
            team_id=team,
            start_ms=start,
            end_ms=end,
            minutes=round((end - start) / MIN_MS, 2),
            possession_time_based=_num(m["possession"]),
            field_tilt=_num(m["field_tilt"]),
            ppda=_num(m["ppda"], 2),
            pass_completion=_num(m["pass_completion"]),
            passes=int(own["passes"]),
            avg_pass_length_m=_num(m["avg_pass_length"], 1),
            width_m=_num(m["width"], 1),
            flank_share_left=_num(m["flank_attack_share_left"]),
            flank_share_right=_num(m["flank_attack_share_right"]),
            shots=int(own["shots"]),
            goals=goals,
            xg=round(xg, 3),
            xt_added=round(xt, 3),
            control_index=_num(ctrl, 1),
        )

    def compare_windows(
        self,
        team_id: str,
        before_start_ms: int,
        before_end_ms: int,
        after_start_ms: int,
        after_end_ms: int,
    ) -> WindowComparison:
        a = self.get_window_stats(team_id, before_start_ms, before_end_ms)
        b = self.get_window_stats(team_id, after_start_ms, after_end_ms)
        names = (
            "possession_time_based",
            "field_tilt",
            "ppda",
            "pass_completion",
            "avg_pass_length_m",
            "width_m",
            "flank_share_left",
            "flank_share_right",
            "xg",
            "xt_added",
            "control_index",
        )
        deltas = []
        for n in names:
            va, vb = getattr(a, n), getattr(b, n)
            d = None if va is None or vb is None else round(vb - va, 3)
            deltas.append(MetricDelta(metric=n, before=va, after=vb, delta=d))
        return WindowComparison(
            team_id=team_id,
            before=(a.start_ms, a.end_ms),
            after=(b.start_ms, b.end_ms),
            deltas=deltas,
        )

    def get_player_physical(self, player_id: str, start_ms: int, end_ms: int) -> PlayerPhysical:
        pid = self._player(player_id)
        start, end = self.store.clamp(start_ms, end_ms)
        ph = self.store.physical(pid, start, end)
        _, players = self.store.counters(start, end)
        c = players.get(pid, dict.fromkeys(counters.PLAYER_FIELDS, 0.0))
        return PlayerPhysical(
            player_id=pid,
            start_ms=start,
            end_ms=end,
            minutes_on_pitch=round(ph["minutes_on_pitch"], 2),
            distance_m=round(ph["distance_m"], 1),
            high_intensity_m=round(ph["high_intensity_m"], 1),
            sprints=int(ph["sprints"]),
            top_speed_ms=round(ph["top_speed_ms"], 2),
            top_speed_kmh=round(ph["top_speed_ms"] * 3.6, 1),
            touches=int(c["touches"]),
            passes=int(c["passes"]),
            passes_complete=int(c["passes_complete"]),
            progressive_passes=int(c["prog_passes"]),
        )

    def _seq_event(self, e: dict[str, Any]) -> SequenceEvent:
        en = self.store.enriched.get(e["event_id"])
        return SequenceEvent(
            event_id=e["event_id"],
            t_ms=e["t_ms"],
            type=e["type"],
            player_id=e["player_id"],
            outcome=e["outcome"],
            x=e["x"],
            y=e["y"],
            end_x=e["end_x"],
            end_y=e["end_y"],
            pass_length_m=_num(en.pass_length_m, 1) if en else None,
            pass_progression_m=_num(en.pass_progression_m, 1) if en else None,
            pass_difficulty=_num(en.pass_difficulty) if en else None,
            xg=_num(en.xg) if en else None,
            xt_added=_num(en.xt_added, 4) if en else None,
            ball_speed_ms=e["qualifiers"].get("ball_speed_ms"),
        )

    def get_sequence(self, possession_id: int) -> Sequence:
        evs = [e for e in self.store.events if e["possession_id"] == possession_id]
        if not evs:
            return Sequence(
                possession_id=possession_id, team_id=None, start_ms=None, end_ms=None, events=[]
            )
        team = next(
            (e["team_id"] for e in evs if e["type"] in ("kickoff", "possession_change")), None
        )
        team = team or next((e["team_id"] for e in evs if e["type"] in ("pass", "carry")), None)
        return Sequence(
            possession_id=possession_id,
            team_id=team,
            start_ms=evs[0]["t_ms"],
            end_ms=evs[-1]["t_ms"],
            events=[self._seq_event(e) for e in evs if e["type"] != "pressure"],
        )

    def get_moment_context(self, t_ms: int) -> MomentContext:
        st = self.store
        t = min(t_ms, max(0, st.now_ms))
        clock, period = self.clock(t)
        recent = [
            e for e in st.events_between(max(0, t - 30_000), t + 1) if e["type"] != "pressure"
        ][-10:]
        trig = st.triggers_between(max(0, t - 60_000), t + 1)
        score = {
            team: sum(
                1
                for e in st.events_between(0, t + 1)
                if e["type"] == "goal" and e["team_id"] == team
            )
            for team in st.team_ids
        }
        return MomentContext(
            t_ms=t,
            clock=clock,
            period=period,
            score=score,
            recent_events=[self._seq_event(e) for e in recent],
            recent_triggers=[TriggerOut(**vars(x)) for x in trig],
            last_5_min={
                team: self.get_window_stats(team, max(0, t - 5 * MIN_MS), t + 1)
                for team in st.team_ids
            },
            last_15_min={
                team: self.get_window_stats(team, max(0, t - 15 * MIN_MS), t + 1)
                for team in st.team_ids
            },
        )
