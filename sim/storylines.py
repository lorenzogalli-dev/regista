"""Hidden storylines: parameter modifiers over time windows (SPEC §3.5).

The engine asks `Modifiers` for effective parameters at time t. Nothing here is visible
to agents; `ground_truth()` is written only to the ground-truth directory.
"""

from dataclasses import dataclass, field

import numpy as np

from sim.roster import LINE, WIDE, TeamSheet
from sim.schema import ExpectedSignal, GroundTruth, Storyline, StorylineType

MIN = 60_000

TYPES: tuple[StorylineType, ...] = (
    "pressing_spell",
    "fatigue_drop",
    "momentum_shift",
    "tactical_switch",
    "player_arc",
)
# Types the simulator currently generates. pressing_spell and fatigue_drop are implemented
# but disabled: in the final signal check (docs/signal_check.md) their median z was below 2,
# i.e. not reliably distinguishable from noise.
ACTIVE_TYPES: tuple[StorylineType, ...] = ("momentum_shift", "tactical_switch", "player_arc")
DURATION_MIN: dict[StorylineType, tuple[int, int]] = {
    "pressing_spell": (14, 20),
    "fatigue_drop": (15, 22),
    "momentum_shift": (14, 20),
    "tactical_switch": (16, 22),
    "player_arc": (18, 25),
}


@dataclass
class Plan:
    """A realised storyline plus the engine-side parameters it implies."""

    sl: Storyline
    side: int  # 0 = home, 1 = away (the team the storyline is about)
    player_slot: int | None = None  # starter index for player storylines
    trigger: str | None = None  # momentum_shift: "red_card" | "sub"
    trigger_player: str | None = None  # player sent off, or player brought on


@dataclass
class Modifiers:
    plans: list[Plan] = field(default_factory=list)

    def _active(self, t_ms: int) -> list[Plan]:
        return [p for p in self.plans if p.sl.start_ms <= t_ms < p.sl.end_ms]

    def press(self, side: int, base: float, t_ms: int) -> float:
        v = base
        for p in self._active(t_ms):
            if p.sl.type == "pressing_spell" and p.side == side:
                v = 0.97
            if p.sl.type == "momentum_shift":
                v = min(1.0, v + 0.25) if p.side == side else max(0.1, v - 0.2)
        return v

    def directness(self, side: int, base: float, t_ms: int) -> float:
        for p in self._active(t_ms):
            if p.sl.type == "tactical_switch" and p.side == side and p.sl.variant == "long_ball":
                return 0.92
        return base

    def width(self, side: int, base: float, t_ms: int) -> float:
        for p in self._active(t_ms):
            if p.sl.type == "tactical_switch" and p.side == side and p.sl.variant == "wide":
                return 0.97
        return base

    def retention(self, side: int, t_ms: int) -> float:
        """Additive logit on pass success for this side."""
        v = 0.0
        for p in self._active(t_ms):
            if p.sl.type == "momentum_shift":
                v += 1.2 if p.side == side else -1.0
        return v

    def extra_fatigue(self, side: int, slot: int, t_ms: int) -> float:
        """Additional top-speed loss (fraction) for a fatigue_drop target."""
        for p in self.plans:
            if p.sl.type == "fatigue_drop" and p.side == side and p.player_slot == slot:
                if t_ms < p.sl.start_ms:
                    return 0.0
                return 0.25 * min(1.0, (t_ms - p.sl.start_ms) / (6 * MIN))
        return 0.0

    def hold_factor(self, side: int, t_ms: int) -> float:
        """Multiplier on how long a player keeps the ball before acting."""
        for p in self._active(t_ms):
            if p.sl.type == "momentum_shift":
                return 1.25 if p.side == side else 0.85
        return 1.0

    def block_shift(self, side: int, t_ms: int) -> float:
        """Shift of the team's shape towards the opponent goal (fraction of pitch length)."""
        for p in self._active(t_ms):
            if p.sl.type == "momentum_shift":
                return 0.08 if p.side == side else -0.10
            if p.sl.type == "pressing_spell" and p.side == side:
                return 0.06  # the whole team plays higher, not only the block
        return 0.0

    def flank_target(self, attacking_side: int, t_ms: int) -> tuple[int, int] | None:
        """(defending side, slot) of a tiring player whose flank the attackers should target."""
        for p in self._active(t_ms):
            if (
                p.sl.type == "fatigue_drop"
                and p.side != attacking_side
                and p.player_slot is not None
            ):
                return p.side, p.player_slot
        return None

    def playmaker(self, side: int, t_ms: int) -> int | None:
        for p in self._active(t_ms):
            if p.sl.type == "player_arc" and p.side == side:
                return p.player_slot
        return None

    def protected_slots(self, side: int) -> set[int]:
        """Starters that must stay on the pitch through their storyline."""
        return {p.player_slot for p in self.plans if p.side == side and p.player_slot is not None}


def clock_minute(t_ms: int, period_ends: list[int]) -> int:
    """Broadcast clock minute: the second half restarts at 45 regardless of first-half stoppage."""
    if t_ms < period_ends[0]:
        return t_ms // MIN
    return 45 + (t_ms - period_ends[0]) // MIN


def _windows(
    rng: np.random.Generator, types: list[StorylineType], period_ends: list[int]
) -> list[tuple[int, int]] | None:
    """Non-overlapping windows, each inside one period, at least 4 minutes apart."""
    p1_end = period_ends[0]
    spans = [(8 * MIN, p1_end - 2 * MIN), (p1_end + 5 * MIN, period_ends[1] - 4 * MIN)]
    chosen: list[tuple[int, int]] = []
    for t in types:
        lo_d, hi_d = DURATION_MIN[t]
        dur = int(rng.integers(lo_d, hi_d + 1)) * MIN
        for _ in range(50):
            s_lo, s_hi = spans[int(rng.integers(2))]
            if s_hi - s_lo <= dur:
                continue
            start = int(rng.integers(s_lo // MIN, (s_hi - dur) // MIN + 1)) * MIN
            end = start + dur
            if all(end + 4 * MIN <= a or start >= b + 4 * MIN for a, b in chosen):
                chosen.append((start, end))
                break
        else:
            return None
    return chosen


def plan(
    rng: np.random.Generator,
    home: TeamSheet,
    away: TeamSheet,
    period_ends: list[int],
    control: bool,
    pool: tuple[StorylineType, ...] = ACTIVE_TYPES,
) -> Modifiers:
    """Draw 2-3 storylines from `pool` (disabled types can still be drawn explicitly)."""
    if control:
        return Modifiers()
    while True:
        n = int(rng.integers(2, 4))
        types = [pool[int(i)] for i in rng.choice(len(pool), size=n, replace=False)]
        wins = _windows(rng, types, period_ends)
        if wins is not None:
            break
    plans = [
        _make(rng, i, t, w, home, away, period_ends)
        for i, (t, w) in enumerate(zip(types, wins, strict=True))
    ]
    plans.sort(key=lambda p: p.sl.start_ms)
    return Modifiers(plans)


def _make(
    rng: np.random.Generator,
    idx: int,
    t: StorylineType,
    win: tuple[int, int],
    home: TeamSheet,
    away: TeamSheet,
    period_ends: list[int],
) -> Plan:
    side = int(rng.integers(2))
    sheet, opp = (home, away) if side == 0 else (away, home)
    team, other = sheet.team, opp.team
    sid = f"s_{idx + 1:02d}"
    start, end = win
    minute = clock_minute(start, period_ends)
    sig = ExpectedSignal

    if t == "pressing_spell":
        sl = Storyline(
            storyline_id=sid,
            type=t,
            start_ms=start,
            end_ms=end,
            team_id=team.team_id,
            actors=[],
            mechanism={
                "press_intensity": f"{team.style.press_intensity} -> 0.97",
                "shape": "higher block and line, one extra presser, more tackles",
            },
            expected_signals=[
                sig(metric="ppda", team=team.team_id, direction="down"),
                sig(metric="pass_completion", team=other.team_id, direction="down"),
                sig(metric="field_tilt", team=team.team_id, direction="up"),
            ],
            canonical_explanation=(
                f"{team.name} raised their press from minute {minute}; "
                f"{other.name}'s build-up broke down and play tilted into their half."
            ),
        )
        return Plan(sl, side)

    if t == "fatigue_drop":
        slots = [i for i, p in enumerate(sheet.players[:11]) if p.position in WIDE]
        slot = slots[int(rng.integers(len(slots)))]
        pl = sheet.players[slot]
        sl = Storyline(
            storyline_id=sid,
            type=t,
            start_ms=start,
            end_ms=end,
            team_id=team.team_id,
            actors=[pl.player_id],
            mechanism={
                "top_speed": "-25% over 6 min",
                "sprints": "fewer, shorter",
                "opponent_targeting": "flank of tiring player",
            },
            expected_signals=[
                sig(metric="top_speed", player=pl.player_id, direction="down"),
                sig(metric="sprint_count", player=pl.player_id, direction="down"),
                sig(metric="flank_attack_share", team=other.team_id, direction="up"),
            ],
            canonical_explanation=(
                f"{pl.name} tired visibly from minute {minute}; {other.name} kept attacking that "
                f"flank until {pl.name} was substituted."
            ),
        )
        return Plan(sl, side, player_slot=slot)

    if t == "momentum_shift":
        trigger = "red_card" if rng.random() < 0.5 else "sub"
        if trigger == "red_card":
            # The beneficiary is `team`; the opponent receives the red card.
            outfield = [i for i, p in enumerate(opp.players[:11]) if LINE[p.position] != "GK"]
            culprit = opp.players[outfield[int(rng.integers(len(outfield)))]]
            actors = [culprit.player_id]
            cause = f"{other.name} went down to ten men ({culprit.name} sent off)"
        else:
            bench = sheet.players[11:]
            sub_in = [p for p in bench if LINE[p.position] != "GK"][int(rng.integers(4))]
            actors = [sub_in.player_id]
            cause = f"{team.name} brought on {sub_in.name}"
        sl = Storyline(
            storyline_id=sid,
            type=t,
            variant=trigger,
            start_ms=start,
            end_ms=end,
            team_id=team.team_id,
            actors=actors,
            mechanism={
                "trigger": trigger,
                "press_intensity": "+0.25",
                "retention": "+1.2 / -1.0 logit",
                "tempo": "beneficiary keeps the ball longer, opponent loses it more",
                "shape": "beneficiary higher, opponent deeper",
            },
            expected_signals=[
                sig(metric="possession", team=team.team_id, direction="up"),
                sig(metric="field_tilt", team=team.team_id, direction="up"),
            ],
            canonical_explanation=(
                f"Momentum swung in minute {minute}: {cause}, and {team.name} took control "
                f"of the ball and territory."
            ),
        )
        return Plan(sl, side, trigger=trigger, trigger_player=actors[0])

    if t == "tactical_switch":
        variant = "long_ball" if rng.random() < 0.5 else "wide"
        if variant == "long_ball":
            mech = {
                "directness": f"{team.style.directness} -> 0.92",
                "long_balls": "70% of passes before the final third go long to the front player",
            }
            sigs = [
                sig(metric="avg_pass_length", team=team.team_id, direction="up"),
                sig(metric="pass_completion", team=team.team_id, direction="down"),
            ]
            text = (
                f"{team.name} switched to long balls from minute {minute}, "
                "trading control for directness."
            )
        else:
            mech = {"width": f"{team.style.width} -> 0.97", "passing": "wide receivers preferred"}
            sigs = [sig(metric="width", team=team.team_id, direction="up")]
            text = (
                f"{team.name} stretched the pitch from minute {minute}, "
                "pushing play out to the flanks."
            )
        sl = Storyline(
            storyline_id=sid,
            type=t,
            variant=variant,
            start_ms=start,
            end_ms=end,
            team_id=team.team_id,
            actors=[],
            mechanism=mech,
            expected_signals=sigs,
            canonical_explanation=text,
        )
        return Plan(sl, side)

    # player_arc: a playmaker spell
    slots = [i for i, p in enumerate(sheet.players[:11]) if LINE[p.position] == "MID"]
    slot = slots[int(rng.integers(len(slots)))]
    pl = sheet.players[slot]
    sl = Storyline(
        storyline_id=sid,
        type=t,
        variant="playmaker",
        start_ms=start,
        end_ms=end,
        team_id=team.team_id,
        actors=[pl.player_id],
        mechanism={
            "passing": "+0.25",
            "involvement": "team-mates look for this player",
            "progression": "x3",
        },
        expected_signals=[
            sig(metric="progressive_passes", player=pl.player_id, direction="up"),
            sig(metric="touches", player=pl.player_id, direction="up"),
        ],
        canonical_explanation=(
            f"{pl.name} took over the midfield from minute {minute}, driving {team.name} "
            f"forward with a run of progressive passes."
        ),
    )
    return Plan(sl, side, player_slot=slot)


def ground_truth(match_id: str, seed: int, control: bool, mods: Modifiers) -> GroundTruth:
    return GroundTruth(
        match_id=match_id, seed=seed, control=control, storylines=[p.sl for p in mods.plans]
    )
