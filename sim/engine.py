"""Match engine: one 10 Hz loop that produces events and tracking together (SPEC §4).

Ball logic is a small state machine (held / flight / dead). Player movement is
vectorised over the 22 slots: formation anchors shifted by ball position and phase,
plus pressers, runners, the ball carrier and pass receivers.

All probabilities here are the simulator's hidden "true" model. The metrics engine
never reads them; it re-derives its own estimates (e.g. xG) from the output.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from sim import pitch
from sim.roster import LINE, TeamSheet
from sim.schema import PITCH_LENGTH, PITCH_WIDTH, TICK_MS, MatchMeta, Player
from sim.storylines import MIN, Modifiers

DT = TICK_MS / 1000.0
N_SLOTS = 22
OFF_PITCH = (-5.0, -5.0)

BallMode = Literal["held", "flight", "dead"]


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


@dataclass
class Flight:
    kind: Literal["pass", "shot", "clearance", "loose"]
    start: tuple[float, float]
    end: tuple[float, float]
    t0: int
    t1: int
    speed: float
    peak_z: float
    to_slot: int | None  # who takes it at the end (None = resolved on arrival)
    outcome: str = ""
    shooter_side: int = 0


@dataclass
class Restart:
    at: int
    slot: int
    pos: tuple[float, float]
    kind: str


@dataclass
class SimResult:
    meta: MatchMeta
    events: list[dict[str, Any]]
    t_ms: np.ndarray  # (T,)
    period: np.ndarray  # (T,)
    ball: np.ndarray  # (T, 4): x, y, z, speed
    pos: np.ndarray  # (T, 22, 2)
    speed: np.ndarray  # (T, 22)
    slot_player: np.ndarray  # (T, 22) index into meta.players, -1 when the slot is empty
    score: tuple[int, int] = (0, 0)
    timings: dict[str, float] = field(default_factory=dict)


class Engine:
    def __init__(
        self,
        meta: MatchMeta,
        home: TeamSheet,
        away: TeamSheet,
        mods: Modifiers,
        rng: np.random.Generator,
        noise: np.random.Generator,
    ) -> None:
        self.meta = meta
        self.sheets = (home, away)
        self.mods = mods
        self.rng = rng
        self.noise = noise
        self.players: list[Player] = meta.players
        self.pidx = {p.player_id: i for i, p in enumerate(self.players)}
        self.period_ends = meta.period_end_ms

        n_home = len(home.players)
        self.side = np.array([0] * 11 + [1] * 11)
        self.slot_pid = np.array(list(range(11)) + [n_home + i for i in range(11)])
        self.active = np.ones(N_SLOTS, dtype=bool)
        self.anchor = np.array(home.anchors + away.anchors, dtype=float)
        self.is_gk = np.array([LINE[self.players[i].position] == "GK" for i in self.slot_pid])
        self.entry_ms = np.zeros(N_SLOTS)
        self._load_attrs()

        self.pos = np.zeros((N_SLOTS, 2))
        self.vel = np.zeros((N_SLOTS, 2))
        self.run_until = np.zeros(N_SLOTS, dtype=np.int64)
        self.stun_until = np.zeros(N_SLOTS, dtype=np.int64)

        self.t = 0
        self.period = 1
        self.score = [0, 0]
        self.events: list[dict[str, Any]] = []
        self.possession_id = 0
        self.poss_side = 0
        self.mode: BallMode = "dead"
        self.holder = -1
        self.ball = np.array([PITCH_LENGTH / 2, PITCH_WIDTH / 2])
        self.ball_z = 0.0
        self.ball_speed = 0.0
        self.flight: Flight | None = None
        self.restart: Restart | None = None
        self.decide_at = 0
        self.hold_start = (0.0, 0.0)
        self.hold_pressed: set[int] = set()
        self.hold_engaged: set[int] = set()
        self.last_pass_high = False
        self.last_change_t = -(10**9)
        self.yellows: dict[int, int] = {}
        self.subs_used = [0, 0]
        self.used_bench: set[int] = set()
        self._schedule()

    # ------------------------------------------------------------------ setup

    def _load_attrs(self) -> None:
        a = [self.players[i].attrs for i in self.slot_pid]
        self.top = np.array([x.top_speed_ms for x in a])
        self.accel = np.array([x.accel for x in a])
        self.passing = np.array([x.passing for x in a])
        self.finishing = np.array([x.finishing for x in a])
        self.defending = np.array([x.defending for x in a])
        self.stamina = np.array([x.stamina for x in a])

    def _set_slot_attrs(self, slot: int) -> None:
        x = self.players[int(self.slot_pid[slot])].attrs
        self.top[slot], self.accel[slot], self.passing[slot] = x.top_speed_ms, x.accel, x.passing
        self.finishing[slot], self.defending[slot], self.stamina[slot] = (
            x.finishing,
            x.defending,
            x.stamina,
        )

    def _schedule(self) -> None:
        """Scheduled substitutions and storyline triggers, as (t_ms, kind, data)."""
        p1 = self.period_ends[0]
        self.jobs: list[tuple[int, str, Any]] = []
        reserved = [0, 0]
        for plan in self.mods.plans:
            sl = plan.sl
            if sl.type == "fatigue_drop":
                self.jobs.append((sl.end_ms, "forced_sub", (plan.side, plan.player_slot)))
                reserved[plan.side] += 1
            if sl.type == "momentum_shift":
                self.jobs.append((sl.start_ms, "trigger", plan))
                if plan.trigger == "sub":
                    reserved[plan.side] += 1
        for side in (0, 1):
            n = 3 - reserved[side]
            for m in sorted(self.rng.uniform(58, 85, size=n)):
                self.jobs.append((p1 + int((m - 45) * MIN), "sub", side))
        self.jobs.sort(key=lambda j: j[0])

    # ------------------------------------------------------------------ helpers

    def _dir(self, side: int) -> int:
        return pitch.direction(side == 0, self.period)

    def _line(self, slot: int) -> str:
        return LINE[self.players[int(self.slot_pid[slot])].position]

    def _pid(self, slot: int) -> str:
        return self.players[int(self.slot_pid[slot])].player_id

    def _team_id(self, side: int) -> str:
        return self.sheets[side].team.team_id

    def _style(self, side: int) -> tuple[float, float, float]:
        st = self.sheets[side].team.style
        return (
            self.mods.press(side, st.press_intensity, self.t),
            self.mods.directness(side, st.directness, self.t),
            self.mods.width(side, st.width, self.t),
        )

    def _side_slots(self, side: int) -> np.ndarray:
        idx = np.arange(side * 11, side * 11 + 11)
        return idx[self.active[idx]]

    def _emit(
        self,
        type_: str,
        slot: int | None,
        x: float,
        y: float,
        *,
        side: int | None = None,
        end: tuple[float, float] | None = None,
        outcome: str | None = None,
        recipient: int | None = None,
        **qualifiers: Any,
    ) -> None:
        if side is None and slot is not None:
            side = int(self.side[slot])
        self.events.append(
            {
                "event_id": f"e_{len(self.events) + 1:06d}",
                "match_id": self.meta.match_id,
                "t_ms": self.t,
                "period": self.period,
                "type": type_,
                "team_id": self._team_id(side) if side is not None else None,
                "player_id": self._pid(slot) if slot is not None else None,
                "x": round(float(x), 2),
                "y": round(float(y), 2),
                "end_x": round(float(end[0]), 2) if end else None,
                "end_y": round(float(end[1]), 2) if end else None,
                "outcome": outcome,
                "recipient_id": self._pid(recipient) if recipient is not None else None,
                "possession_id": self.possession_id,
                "qualifiers": qualifiers,
            }
        )

    def _gain(self, slot: int, *, emit_change: bool = True) -> None:
        """Give the ball to `slot`; a side change opens a new possession."""
        side = int(self.side[slot])
        if side != self.poss_side:
            self.poss_side = side
            self.possession_id += 1
            self.last_change_t = self.t
            if emit_change:
                self._emit("possession_change", slot, *self.pos[slot])
            self._transition_runs(side)
        self._hold(slot)

    def _hold(self, slot: int) -> None:
        self.mode = "held"
        self.holder = slot
        self.flight = None
        self.ball[:] = self.pos[slot]
        self.ball_z = 0.0
        self.hold_start = (float(self.pos[slot, 0]), float(self.pos[slot, 1]))
        self.hold_pressed = set()
        self.hold_engaged = set()
        if self.is_gk[slot]:
            base = 4.0
        elif self._line(slot) == "FWD":
            base = float(self.rng.uniform(1.5, 3.2))
        else:
            base = float(self.rng.uniform(3.0, 5.8))
        press_opp = self._style(1 - int(self.side[slot]))[0]
        base *= 1.0 - 0.5 * max(0.0, press_opp - 0.5)
        base *= self.mods.hold_factor(int(self.side[slot]), self.t)
        self.decide_at = self.t + int(base * 1000)

    def _transition_runs(self, side: int) -> None:
        """On a turnover, attackers of the new side burst forward and the others recover."""
        for s in self._side_slots(side):
            fwd = LINE[self.players[int(self.slot_pid[s])].position] == "FWD"
            if self.rng.random() < (0.5 if fwd else 0.12):
                self.run_until[s] = self.t + int(self.rng.uniform(2000, 4000))
        for s in self._side_slots(1 - side):
            if not self.is_gk[s] and self.rng.random() < 0.15:
                self.run_until[s] = self.t + int(self.rng.uniform(1500, 3000))

    def _opp_min_dist(self, point: np.ndarray, side: int) -> tuple[float, int]:
        opp = self._side_slots(1 - side)
        d = np.hypot(*(self.pos[opp] - point).T)
        i = int(np.argmin(d))
        return float(d[i]), int(opp[i])

    def _lane(
        self, a: np.ndarray, b: np.ndarray, side: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Opponent slots, their distance to segment a→b and the projection parameter."""
        opp = self._side_slots(1 - side)
        ab = b - a
        L2 = float(ab @ ab) or 1e-6
        tt = np.clip(((self.pos[opp] - a) @ ab) / L2, 0.0, 1.0)
        proj = a + tt[:, None] * ab
        d = np.hypot(*(self.pos[opp] - proj).T)
        return opp, d, tt

    def _fatigue(self) -> np.ndarray:
        mins = (self.t - self.entry_ms) / MIN
        f = 1.0 - (0.02 + 0.08 * (1.0 - self.stamina)) * (mins / 95.0)
        for side in (0, 1):
            for p in self.mods.plans:
                if p.sl.type == "fatigue_drop" and p.side == side and p.player_slot is not None:
                    slot = side * 11 + p.player_slot
                    f[slot] -= self.mods.extra_fatigue(side, p.player_slot, self.t)
        return np.clip(f, 0.6, 1.0)

    # ------------------------------------------------------------------ main loop

    def run(self) -> SimResult:
        frames_t, frames_p, frames_ball, frames_pos, frames_speed, frames_slot = (
            [],
            [],
            [],
            [],
            [],
            [],
        )
        start = 0
        for period, end in ((1, self.period_ends[0]), (2, self.period_ends[1])):
            self.period = period
            self.t = start
            self._kickoff_setup(kicking_side=0 if period == 1 else 1, teleport=True)
            self._emit("period_start", None, PITCH_LENGTH / 2, PITCH_WIDTH / 2)
            while self.t < end:
                self._step()
                frames_t.append(self.t)
                frames_p.append(period)
                frames_ball.append((self.ball[0], self.ball[1], self.ball_z, self.ball_speed))
                frames_pos.append(np.where(self.active[:, None], self.pos, OFF_PITCH))
                frames_speed.append(np.where(self.active, np.hypot(*self.vel.T), 0.0))
                frames_slot.append(np.where(self.active, self.slot_pid, -1))
                self.t += TICK_MS
            self._emit("period_end", None, *self.ball)
            start = end
        return SimResult(
            meta=self.meta,
            events=self.events,
            t_ms=np.array(frames_t, dtype=np.int64),
            period=np.array(frames_p, dtype=np.int8),
            ball=np.array(frames_ball),
            pos=np.array(frames_pos),
            speed=np.array(frames_speed),
            slot_player=np.array(frames_slot, dtype=np.int16),
            score=(self.score[0], self.score[1]),
        )

    def _step(self) -> None:
        if self.mode != "flight":
            self._run_jobs()
        if self.mode == "held":
            self._step_held()
        elif self.mode == "flight":
            self._step_flight()
        else:
            self._step_dead()
        self._move()
        if self.mode == "held":
            h = self.holder
            v = self.vel[h]
            sp = float(np.hypot(*v))
            self.ball[:] = self.pos[h] + (v / sp * 0.6 if sp > 0.3 else 0.0)
            self.ball_speed = sp
            self.ball_z = 0.0

    # ------------------------------------------------------------------ jobs

    def _run_jobs(self) -> None:
        while self.jobs and self.jobs[0][0] <= self.t:
            _, kind, data = self.jobs.pop(0)
            if kind == "sub":
                self._substitute(data, None)
            elif kind == "forced_sub":
                side, starter = data
                self._substitute(side, side * 11 + starter)
            elif kind == "trigger":
                self._trigger(data)

    def _substitute(self, side: int, slot: int | None, bench_pid: str | None = None) -> None:
        if self.subs_used[side] >= 3:
            return
        protected = {side * 11 + s for s in self.mods.protected_slots(side)}
        # A player due to be sent off by a storyline stays on until then.
        red = {p.trigger_player for p in self.mods.plans if p.trigger == "red_card"}
        protected |= {int(s) for s in self._side_slots(side) if self._pid(int(s)) in red}
        if slot is None:
            cands = [
                int(s)
                for s in self._side_slots(side)
                if not self.is_gk[s] and s not in protected and self.entry_ms[s] == 0
            ]
            if not cands:
                return
            slot = min(cands, key=lambda s: (self.stamina[s], s))
        if not self.active[slot]:
            return
        out_pid = int(self.slot_pid[slot])
        line = LINE[self.players[out_pid].position]
        sheet = self.sheets[side]
        base = 0 if side == 0 else len(self.sheets[0].players)
        bench = [base + i for i in range(11, len(sheet.players)) if base + i not in self.used_bench]
        bench = [b for b in bench if LINE[self.players[b].position] != "GK"]
        if bench_pid is not None:
            bench = [self.pidx[bench_pid]]
        if not bench:
            return
        same = [b for b in bench if LINE[self.players[b].position] == line]
        new_pid = (same or bench)[0]
        self.used_bench.add(new_pid)
        self.subs_used[side] += 1
        self._emit(
            "sub",
            slot,
            *self.pos[slot],
            recipient=None,
            player_in=self.players[new_pid].player_id,
            player_out=self.players[out_pid].player_id,
        )
        self.slot_pid[slot] = new_pid
        self.entry_ms[slot] = self.t
        self._set_slot_attrs(slot)

    def _trigger(self, plan: Any) -> None:
        if plan.trigger == "sub":
            side = plan.side
            cands = [
                int(s)
                for s in self._side_slots(side)
                if not self.is_gk[s] and self.entry_ms[s] == 0
            ]
            protected = {side * 11 + s for s in self.mods.protected_slots(side)}
            cands = [s for s in cands if s not in protected] or cands
            slot = min(cands, key=lambda s: (self.stamina[s], s))
            self._substitute(side, slot, bench_pid=plan.trigger_player)
            return
        # red card for the opponent of the beneficiary
        pid = self.pidx[plan.trigger_player]
        slots = np.nonzero((self.slot_pid == pid) & self.active)[0]
        if len(slots) == 0:
            return
        culprit = int(slots[0])
        x, y = self.pos[culprit]
        self._emit("foul", culprit, x, y)
        self._send_off(culprit)
        self._set_restart(1 - int(self.side[culprit]), (float(x), float(y)), "free_kick", 15000)

    def _send_off(self, slot: int) -> None:
        self._emit("card", slot, *self.pos[slot], outcome="red")
        if self.mode == "held" and self.holder == slot:
            self.mode = "dead"
        self.active[slot] = False
        self.pos[slot] = OFF_PITCH
        self.vel[slot] = 0.0

    # ------------------------------------------------------------------ dead ball

    def _kickoff_setup(self, kicking_side: int, teleport: bool) -> None:
        kicker_slots = self._side_slots(kicking_side)
        mids = [s for s in kicker_slots if not self.is_gk[s]]
        kicker = int(max(mids, key=lambda s: self.anchor[s, 0]))
        self.ball[:] = (PITCH_LENGTH / 2, PITCH_WIDTH / 2)
        self.ball_speed = 0.0
        self.mode = "dead"
        self.restart = Restart(
            at=self.t + (0 if teleport else 40000),
            slot=kicker,
            pos=(PITCH_LENGTH / 2, PITCH_WIDTH / 2),
            kind="kickoff",
        )
        if teleport:
            for s in np.nonzero(self.active)[0]:
                self.pos[s] = self._kickoff_spot(int(s))
                self.vel[s] = 0.0
            self.pos[kicker] = (PITCH_LENGTH / 2, PITCH_WIDTH / 2)

    def _kickoff_spot(self, s: int) -> tuple[float, float]:
        ax, ay = self.anchor[s]
        ax = min(0.47, ax * 0.75)
        d = self._dir(int(self.side[s]))
        return pitch.from_attacking(ax * PITCH_LENGTH, ay * PITCH_WIDTH, d)

    def _set_restart(
        self, side: int, at_pos: tuple[float, float], kind: str, delay_ms: int
    ) -> None:
        x = min(max(at_pos[0], 0.0), PITCH_LENGTH)
        y = min(max(at_pos[1], 0.0), PITCH_WIDTH)
        cands = [s for s in self._side_slots(side) if not self.is_gk[s]]
        if kind == "goal_kick":
            cands = [s for s in self._side_slots(side) if self.is_gk[s]] or cands
        dists = [math.hypot(*(self.pos[s] - (x, y))) for s in cands]
        slot = int(cands[int(np.argmin(dists))])
        self.mode = "dead"
        self.holder = -1
        self.flight = None
        self.ball[:] = (x, y)
        self.ball_z = 0.0
        self.ball_speed = 0.0
        self.restart = Restart(at=self.t + delay_ms, slot=slot, pos=(x, y), kind=kind)
        if side != self.poss_side:
            self.poss_side = side
            self.possession_id += 1
            self.last_change_t = self.t
            self._emit("possession_change", slot, x, y)

    def _step_dead(self) -> None:
        r = self.restart
        if r is None or self.t < r.at or not self.active[r.slot]:
            if r is not None and not self.active[r.slot]:
                self._set_restart(int(self.side[r.slot]), r.pos, r.kind, 3000)
            return
        self.pos[r.slot] = r.pos
        self.vel[r.slot] = 0.0
        side = int(self.side[r.slot])
        if r.kind == "kickoff":
            self.poss_side = side
            self.possession_id += 1
            self._emit("kickoff", r.slot, *r.pos)
        self.restart = None
        self._hold(r.slot)
        self.decide_at = self.t + (300 if r.kind == "kickoff" else int(self.rng.uniform(800, 1800)))

    # ------------------------------------------------------------------ ball held

    def _step_held(self) -> None:
        h = self.holder
        side = int(self.side[h])
        press, _, _ = self._style(1 - side)
        opp = self._side_slots(1 - side)
        d = np.hypot(*(self.pos[opp] - self.pos[h]).T)
        for o, dist in zip(opp, d, strict=True):
            o = int(o)
            if dist < 2.5 and o not in self.hold_pressed and not self.is_gk[o]:
                self.hold_pressed.add(o)
                self._emit("pressure", o, *self.pos[o])
        dmin = float(d.min()) if len(d) else 99.0
        if dmin < 2.0 and self.t < self.decide_at - 400:
            self.decide_at -= 150  # rushed under pressure
        for o, dist in zip(opp, d, strict=True):
            o = int(o)
            # One tackle decision per defender per hold, taken when they first get close.
            if dist < 1.5 and o not in self.hold_engaged and not self.is_gk[o]:
                self.hold_engaged.add(o)
                if self.t < self.stun_until[o]:
                    continue
                p = 0.046 * (0.4 + 1.2 * press) * (0.8 + 0.5 * self.defending[o])
                if press > 0.9:
                    p *= 1.5  # an all-out press engages more often
                if self.rng.random() < p:
                    self._tackle(o, h)
                    return
        squeeze = 0.007 * (0.5 + press) * (1.3 - self.passing[h])
        squeeze *= 1.0 - 0.4 * self.mods.retention(side, self.t)
        if dmin < 1.5 and self.rng.random() < squeeze:
            self._lose_control(h)
            return
        if self.t >= self.decide_at:
            self._act(h, dmin)

    def _lose_control(self, h: int) -> None:
        """Carrier squeezed by a close opponent loses the ball; it runs loose a few metres."""
        self._emit_carry(h)
        a = self.pos[h].copy()
        ang = float(self.rng.uniform(0.0, 2.0 * math.pi))
        dist = float(self.rng.uniform(2.0, 6.0))
        end = a + dist * np.array([math.cos(ang), math.sin(ang)])
        self._launch("loose", a, end, 6.0, False, to_slot=None, outcome="loose")

    def _tackle(self, o: int, h: int) -> None:
        x, y = self.pos[h]
        self._emit_carry(h)
        if self.rng.random() < 0.33:
            self._emit("foul", o, x, y)
            if self.rng.random() < 0.15:
                self.yellows[int(self.slot_pid[o])] = self.yellows.get(int(self.slot_pid[o]), 0) + 1
                if self.yellows[int(self.slot_pid[o])] >= 2:
                    self._send_off(o)
                else:
                    self._emit("card", o, x, y, outcome="yellow")
            delay = int(self.rng.uniform(10000, 25000))
            self._set_restart(int(self.side[h]), (float(x), float(y)), "free_kick", delay)
            return
        p_win = 0.55 + 0.3 * (self.defending[o] - self.passing[h])
        p_win -= 0.2 * self.mods.retention(int(self.side[h]), self.t)
        if self.rng.random() < p_win:
            self._emit("tackle", o, x, y, outcome="won")
            self._gain(o)
            self._maybe_clear(o)
        else:
            self._emit("tackle", o, x, y, outcome="lost")
            self.stun_until[o] = self.t + 1500

    def _emit_carry(self, h: int) -> None:
        sx, sy = self.hold_start
        ex, ey = self.pos[h]
        if math.hypot(ex - sx, ey - sy) >= 3.0:
            self._emit("carry", h, sx, sy, end=(float(ex), float(ey)))

    def _act(self, h: int, dmin: float) -> None:
        side = int(self.side[h])
        d = self._dir(side)
        ax, ay = pitch.to_attacking(float(self.pos[h, 0]), float(self.pos[h, 1]), d)
        dist, angle = pitch.goal_distance_angle(ax, ay)
        self._emit_carry(h)
        p_shot = (
            0.0
            if self.is_gk[h]
            else min(
                0.6, 2.2 * math.exp(-dist / 7.5) * (0.4 + angle) + (0.065 if dist < 27.0 else 0.0)
            )
        )
        lead = self.score[side] - self.score[1 - side]
        if lead >= 2:
            p_shot *= 0.5 if lead == 2 else 0.1  # game management: a comfortable lead eases off
        if self.rng.random() < p_shot:
            self._shoot(h, dist, angle, dmin)
        else:
            self._pass(h, dmin)

    # ------------------------------------------------------------------ passing

    def _pass(self, h: int, dmin: float) -> None:
        side = int(self.side[h])
        d = self._dir(side)
        press_opp, directness, _ = self._style(1 - side)[0], *self._style(side)[1:]
        mates = [int(s) for s in self._side_slots(side) if s != h]
        a = self.pos[h].copy()
        playmaker = self.mods.playmaker(side, self.t)
        pm_slot = side * 11 + playmaker if playmaker is not None else None
        flank = self.mods.flank_target(side, self.t)
        flank_y = None
        if flank is not None:
            fs = flank[0] * 11 + flank[1]
            if self.active[fs]:
                flank_y = float(self.pos[fs, 1])

        carrier_fwd = self._line(h) == "FWD"
        wide_mode = self._style(side)[2] >= 0.9
        scores, feats = [], []
        for r in mates:
            b = self.pos[r] + self.vel[r] * 0.5
            L = float(np.hypot(*(b - a)))
            progress = d * float(b[0] - a[0])
            opp, ld, _ = self._lane(a, b, side)
            lane_def = int(np.sum(ld < 2.0))
            openness = float(np.min(np.hypot(*(self.pos[opp] - b).T))) if len(opp) else 10.0
            prog_w = 0.4 + 1.6 * directness
            if h == pm_slot:
                prog_w *= 3.0
            if carrier_fwd:
                prog_w *= 0.5
            sc = (
                0.05 * progress * prog_w
                - 0.045 * L * (1.4 - directness)
                + 0.3 * min(openness, 8.0)
                - 0.9 * lane_def
            )
            if L < 4.0:
                sc -= 3.0
            if self.is_gk[r]:
                sc -= 1.5
            if r == pm_slot:
                sc += 1.5
            if self._line(r) == "FWD":
                sc -= 1.4
            if abs(float(b[1]) - PITCH_WIDTH / 2) > 18.0:
                sc += 1.3 if wide_mode else 0.3
            if flank_y is not None and abs(float(b[1]) - flank_y) < 15.0:
                sc += 1.6
            if not (0.0 <= b[0] <= PITCH_LENGTH and 0.0 <= b[1] <= PITCH_WIDTH):
                sc -= 2.0
            scores.append(sc)
            feats.append((r, b, L, lane_def, openness, progress))
        w = np.exp(np.array(scores) - max(scores))
        k = int(self.rng.choice(len(mates), p=w / w.sum()))
        r, b, L, lane_def, openness, progress = feats[k]
        ax_carrier, _ = pitch.to_attacking(float(a[0]), float(a[1]), d)
        if directness >= 0.85 and ax_carrier < 75.0 and self.rng.random() < 0.7:
            # Long ball: to the most advanced team-mate, into the space behind them.
            k = int(np.argmax([f[5] for f in feats]))
            r = feats[k][0]
            b = self.pos[r] + np.array([d * float(self.rng.uniform(4.0, 10.0)), 0.0])
            b += np.array([0.0, float(self.rng.normal(0.0, 3.0))])
            L = float(np.hypot(*(b - a)))
            opp, ld, _ = self._lane(a, b, side)
            lane_def = int(np.sum(ld < 2.0))
            openness = float(np.min(np.hypot(*(self.pos[opp] - b).T))) if len(opp) else 10.0

        speed = float(np.clip(7.0 + 0.38 * L + self.rng.normal(0, 1.5), 8.0, 25.0))
        high = L > 32 or (lane_def >= 2 and L > 20)
        passing = self.passing[h] + (0.25 if h == pm_slot else 0.0)
        under_pressure = dmin < 2.5
        logit = (
            2.75
            + 2.0 * (passing - 0.7)
            - 0.05 * (L - 15.0)
            - 0.55 * lane_def
            - 0.6 * under_pressure
            + 0.12 * min(openness, 6.0)
            - 1.8 * (press_opp - 0.5)
            - (0.4 if self._line(r) == "FWD" else 0.0)
            - (0.3 if high else 0.0)
            + self.mods.retention(side, self.t)
        )
        ok = self.rng.random() < _sigmoid(logit)
        self.last_pass_high = high
        quals: dict[str, Any] = {
            "under_pressure": under_pressure,
            "ball_speed_ms": round(speed, 2),
            "height": "high" if high else "ground",
        }
        if ok:
            end = (float(b[0]), float(b[1]))
            self._emit("pass", h, *a, end=end, outcome="complete", recipient=r, **quals)
            self._launch("pass", a, np.array(end), speed, high, to_slot=r)
            self.run_until[r] = max(self.run_until[r], self.t + 1000)
            return
        opp, ld, tt = self._lane(a, b, side)
        j = int(np.argmin(ld))
        if ld[j] < 4.0 and tt[j] > 0.15:
            ip = a + tt[j] * (b - a)
            end = (float(ip[0]), float(ip[1]))
            self._emit("pass", h, *a, end=end, outcome="incomplete", recipient=r, **quals)
            self._launch(
                "pass", a, np.array(end), speed, high, to_slot=int(opp[j]), outcome="interception"
            )
        else:
            land = b + self.rng.normal(0, 4.0, size=2)
            end = (float(land[0]), float(land[1]))
            self._emit("pass", h, *a, end=end, outcome="incomplete", recipient=r, **quals)
            self._launch("loose", a, np.array(end), speed, high, to_slot=None, outcome="loose")

    def _launch(
        self,
        kind: Any,
        a: np.ndarray,
        b: np.ndarray,
        speed: float,
        high: bool,
        to_slot: int | None,
        outcome: str = "",
        shooter_side: int = 0,
    ) -> None:
        L = float(np.hypot(*(b - a)))
        dur = max(200, int(L / (speed * 0.85) * 1000))
        self.mode = "flight"
        self.holder = -1
        self.flight = Flight(
            kind=kind,
            start=(float(a[0]), float(a[1])),
            end=(float(b[0]), float(b[1])),
            t0=self.t,
            t1=self.t + dur,
            speed=speed,
            peak_z=(L / 6.0 if high else 0.0),
            to_slot=to_slot,
            outcome=outcome,
            shooter_side=shooter_side,
        )

    def _step_flight(self) -> None:
        f = self.flight
        assert f is not None
        u = min(1.0, (self.t - f.t0) / max(1, f.t1 - f.t0))
        self.ball[:] = (
            f.start[0] + u * (f.end[0] - f.start[0]),
            f.start[1] + u * (f.end[1] - f.start[1]),
        )
        self.ball_z = 4.0 * f.peak_z * u * (1.0 - u)
        self.ball_speed = f.speed * (1.0 - 0.3 * u)
        if u >= 1.0:
            self._arrive(f)

    def _arrive(self, f: Flight) -> None:
        end = np.array(f.end)
        in_play = 0.0 <= end[0] <= PITCH_LENGTH and 0.0 <= end[1] <= PITCH_WIDTH
        if f.kind == "shot":
            self._shot_arrive(f)
            return
        to = f.to_slot
        if f.kind == "pass" and f.outcome != "interception" and to is not None and self.active[to]:
            self.pos[to] = end
            self._hold(to)
            return
        if f.kind == "pass" and f.outcome == "interception" and f.to_slot is not None:
            s = f.to_slot
            if self.active[s]:
                self.pos[s] = end
                self._emit("interception", s, *end)
                self._gain(s)
                self._maybe_clear(s)
                return
        if not in_play:
            last_side = self.poss_side
            kind = "throw_in" if not (0.0 <= end[1] <= PITCH_WIDTH) else "goal_kick"
            delay = int(
                self.rng.uniform(7000, 14000)
                if kind == "throw_in"
                else self.rng.uniform(10000, 18000)
            )
            self._set_restart(1 - last_side, (float(end[0]), float(end[1])), kind, delay)
            return
        # Loose ball: nearest player wins it; contested balls favour the side out of possession.
        act = np.nonzero(self.active)[0]
        dd = np.hypot(*(self.pos[act] - end).T)
        dd = dd - np.where(self.side[act] != self.poss_side, 1.5, 0.0)
        s = int(act[int(np.argmin(dd))])
        self.pos[s] = end
        if int(self.side[s]) != self.poss_side:
            self._emit("ball_recovery", s, *end)
            self._gain(s)
        else:
            self._hold(s)

    def _maybe_clear(self, s: int) -> None:
        side = int(self.side[s])
        ax, _ = pitch.to_attacking(float(self.pos[s, 0]), float(self.pos[s, 1]), self._dir(side))
        dmin, _ = self._opp_min_dist(self.pos[s], side)
        if ax < 30.0 and dmin < 4.0 and not self.is_gk[s] and self.rng.random() < 0.5:
            d = self._dir(side)
            tax = float(self.rng.uniform(55, 80))
            tay = float(self.rng.uniform(8, 60))
            end = np.array(pitch.from_attacking(tax, tay, d))
            a = self.pos[s].copy()
            self._emit("clearance", s, *a, end=(float(end[0]), float(end[1])))
            self._launch("clearance", a, end, float(self.rng.uniform(18, 25)), True, to_slot=None)
            # possession of a clearance is resolved on arrival as a loose ball
            if self.flight is not None:
                self.flight.kind = "loose"

    # ------------------------------------------------------------------ shooting

    def _shoot(self, h: int, dist: float, angle: float, dmin: float) -> None:
        side = int(self.side[h])
        d = self._dir(side)
        head = self.last_pass_high and dist < 14.0 and self.rng.random() < 0.7
        if head:
            speed = float(self.rng.uniform(15.0, 18.5))
        else:
            speed = float(
                np.clip(
                    self.rng.normal(24.0 + 8.0 * (self.finishing[h] - 0.6), 3.5)
                    - 0.15 * max(0.0, dist - 16.0),
                    15.0,
                    35.0,
                )
            )
        under_pressure = dmin < 2.5
        a = self.pos[h].copy()
        goal = np.array(pitch.from_attacking(PITCH_LENGTH, PITCH_WIDTH / 2, d))
        opp, ld, tt = self._lane(a, goal, side)
        blockers = [
            (int(o), float(t))
            for o, dd, t in zip(opp, ld, tt, strict=True)
            if dd < 1.2 and 0.05 < t < 0.9 and not self.is_gk[o]
        ]
        quals: dict[str, Any] = {
            "body_part": "head" if head else "foot",
            "ball_speed_ms": round(speed, 2),
            "under_pressure": under_pressure,
        }
        if blockers and self.rng.random() < 0.45:
            o, t = blockers[0]
            end = a + t * (goal - a)
            self._emit(
                "shot", h, *a, end=(float(end[0]), float(end[1])), outcome="blocked", **quals
            )
            self._launch(
                "shot", a, end, speed, False, to_slot=o, outcome="blocked", shooter_side=side
            )
            return
        p_goal = _sigmoid(
            -0.85
            - 0.12 * dist
            + 1.5 * angle
            + 2.0 * (self.finishing[h] - 0.6)
            - 0.5 * under_pressure
            - 0.7 * head
        )
        u = self.rng.random()
        keeper = [int(s) for s in self._side_slots(1 - side) if self.is_gk[s]]
        if u < p_goal:
            outcome = "goal"
            gy = PITCH_WIDTH / 2 + float(self.rng.uniform(-3.3, 3.3))
            end = np.array(pitch.from_attacking(PITCH_LENGTH, gy, d))
            to = None
        elif u < p_goal + 0.38 * (1 - p_goal) and keeper:
            outcome = "saved"
            to = keeper[0]
            end = self.pos[to].copy()
        else:
            outcome = "off_target"
            off = float(self.rng.uniform(4.5, 12.0)) * (1 if self.rng.random() < 0.5 else -1)
            end = np.array(pitch.from_attacking(PITCH_LENGTH + 1.0, PITCH_WIDTH / 2 + off, d))
            to = None
        self._emit("shot", h, *a, end=(float(end[0]), float(end[1])), outcome=outcome, **quals)
        self._launch(
            "shot",
            a,
            end,
            speed,
            outcome == "off_target" and self.rng.random() < 0.5,
            to_slot=to,
            outcome=outcome,
            shooter_side=side,
        )

    def _shot_arrive(self, f: Flight) -> None:
        end = np.array(f.end)
        side = f.shooter_side
        if f.outcome == "goal":
            self._emit("goal", None, *end, side=side)
            self.score[side] += 1
            self._kickoff_setup(kicking_side=1 - side, teleport=False)
        elif f.outcome == "saved" and f.to_slot is not None and self.active[f.to_slot]:
            if self.rng.random() < 0.35:
                self._emit("save", f.to_slot, *end, outcome="parried")
                d = self._dir(side)
                flag_y = 0.5 if self.rng.random() < 0.5 else PITCH_WIDTH - 0.5
                corner = pitch.from_attacking(PITCH_LENGTH - 0.5, flag_y, d)
                self._set_restart(side, corner, "corner", int(self.rng.uniform(18000, 28000)))
            else:
                self._emit("save", f.to_slot, *end, outcome="won")
                self._gain(f.to_slot)
        elif f.outcome == "blocked" and f.to_slot is not None and self.active[f.to_slot]:
            self.pos[f.to_slot] = end
            self._gain(f.to_slot)
            self._maybe_clear(f.to_slot)
        else:
            d = self._dir(1 - side)
            spot = pitch.from_attacking(6.0, PITCH_WIDTH / 2, d)
            self._set_restart(1 - side, spot, "goal_kick", int(self.rng.uniform(12000, 20000)))

    # ------------------------------------------------------------------ movement

    def _targets(self) -> tuple[np.ndarray, np.ndarray]:
        """Target positions and desired speeds for every slot."""
        tgt = np.zeros((N_SLOTS, 2))
        want = np.zeros(N_SLOTS)
        ps = self.poss_side
        for side in (0, 1):
            sl = slice(side * 11, side * 11 + 11)
            d = self._dir(side)
            press, _, width = self._style(side)
            bax, bay = pitch.to_attacking(float(self.ball[0]), float(self.ball[1]), d)
            bax /= PITCH_LENGTH
            bay /= PITCH_WIDTH
            ax0, ay0 = self.anchor[sl, 0], self.anchor[sl, 1]
            if side == ps:
                ax = ax0 * 0.95 + 0.40 * (bax - 0.5) + 0.05 + 0.25 * ax0 * max(0.0, bax - 0.55)
                ay = 0.5 + (ay0 - 0.5) * (0.85 + 0.5 * width) + 0.1 * (bay - 0.5)
            else:
                ax = ax0 * 0.85 + 0.35 * (bax - 0.5) - 0.02 + 0.6 * (press - 0.5)
                ay = 0.5 + (ay0 - 0.5) * 0.7 + 0.25 * (bay - 0.5)
            ax = ax + self.mods.block_shift(side, self.t)
            gk = self.is_gk[sl]
            ax = np.where(gk, 0.035 + 0.04 * bax, ax)
            ay = np.where(gk, 0.5 + 0.3 * (bay - 0.5), ay)
            ax = np.clip(ax, 0.02, 0.93) * PITCH_LENGTH
            ay = np.clip(ay, 0.03, 0.97) * PITCH_WIDTH
            if d == -1:
                ax, ay = PITCH_LENGTH - ax, PITCH_WIDTH - ay
            tgt[sl, 0], tgt[sl, 1] = ax, ay
        dist = np.hypot(*(tgt - self.pos).T)
        want[:] = np.clip(0.55 * dist, 0.0, 4.5)

        running = self.run_until > self.t
        if running.any():
            for s in np.nonzero(running & self.active & ~self.is_gk)[0]:
                side = int(self.side[s])
                d = self._dir(side)
                push = 14.0 if side == ps else -12.0
                tgt[s, 0] = np.clip(self.pos[s, 0] + d * push, 2.0, PITCH_LENGTH - 2.0)
                want[s] = self.top[s]

        if self.mode == "dead" and self.restart is not None:
            r = self.restart
            tgt[r.slot] = r.pos
            want[r.slot] = min(
                self.top[r.slot], max(2.0, 0.7 * float(np.hypot(*(self.pos[r.slot] - r.pos))))
            )
            if r.kind == "kickoff":
                for s in np.nonzero(self.active)[0]:
                    if s != r.slot:
                        tgt[s] = self._kickoff_spot(int(s))
                        want[s] = min(4.0, want[s] + 1.0)
            return tgt, want

        # pressers chase the ball
        def_side = 1 - ps
        press, _, _ = self._style(def_side)
        n_press = 1 + int(press * 2.2) + (1 if press > 0.9 else 0)
        cand = [int(s) for s in self._side_slots(def_side) if not self.is_gk[s]]
        if cand:
            dd = np.hypot(*(self.pos[cand] - self.ball).T)
            order = np.argsort(dd, kind="stable")[:n_press]
            for rank, k in enumerate(order):
                s = cand[int(k)]
                if self.t < self.stun_until[s]:
                    continue
                tgt[s] = self.ball
                fast = (
                    (0.55 + 0.35 * press) * self.top[s]
                    if rank == 0
                    else (0.45 + 0.25 * press) * self.top[s]
                )
                want[s] = fast if dd[k] > 2.0 else 2.5

        if self.mode == "held":
            h = self.holder
            side = int(self.side[h])
            d = self._dir(side)
            dmin, _ = self._opp_min_dist(self.pos[h], side)
            tgt[h] = (np.clip(self.pos[h, 0] + d * 8.0, 1.0, PITCH_LENGTH - 1.0), self.pos[h, 1])
            want[h] = 0.0 if self.is_gk[h] else (6.0 if dmin > 6.0 else 2.5)
        elif self.mode == "flight" and self.flight is not None and self.flight.to_slot is not None:
            s = self.flight.to_slot
            tgt[s] = self.flight.end
            want[s] = 0.85 * self.top[s]
        return tgt, want

    def _move(self) -> None:
        tgt, want = self._targets()
        for p in self.mods.plans:
            if p.sl.type == "fatigue_drop" and p.player_slot is not None:
                slot = p.side * 11 + p.player_slot
                if self.mods.extra_fatigue(p.side, p.player_slot, self.t) > 0.05:
                    want[slot] = min(want[slot], 0.70 * self.top[slot])
        delta = tgt - self.pos
        dist = np.hypot(*delta.T)
        unit = delta / np.maximum(dist, 1e-6)[:, None]
        desired = unit * np.minimum(want, dist / DT)[:, None]
        desired += self.noise.normal(0.0, 0.12, size=(N_SLOTS, 2))
        amax = (3.0 + 3.0 * self.accel) * DT
        dv = desired - self.vel
        dvn = np.hypot(*dv.T)
        dv *= np.minimum(1.0, amax / np.maximum(dvn, 1e-6))[:, None]
        self.vel += dv
        cap = self.top * self._fatigue()
        sp = np.hypot(*self.vel.T)
        self.vel *= np.minimum(1.0, cap / np.maximum(sp, 1e-6))[:, None]
        self.vel[~self.active] = 0.0
        self.pos += self.vel * DT
        self.pos[:, 0] = np.clip(self.pos[:, 0], -2.0, PITCH_LENGTH + 2.0)
        self.pos[:, 1] = np.clip(self.pos[:, 1], -2.0, PITCH_WIDTH + 2.0)
        self.pos[~self.active] = OFF_PITCH
