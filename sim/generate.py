"""Build a match from a seed and run the engine."""

import time

from sim import roster, storylines
from sim.engine import Engine, SimResult
from sim.rng import streams
from sim.schema import GroundTruth, MatchMeta
from sim.seeds import is_control
from sim.storylines import MIN


def match_id(seed: int) -> str:
    return f"m_{seed}"


def simulate(seed: int, control: bool | None = None) -> tuple[SimResult, GroundTruth]:
    """Run one full match. `control` defaults to membership of the control seed set."""
    t0 = time.perf_counter()
    if control is None:
        control = is_control(seed)
    rs = streams(seed)
    home, away, venue = roster.build(rs.roster)
    stoppage = [int(x) for x in rs.engine.integers(1, 5, size=2)]
    p1 = (45 + stoppage[0]) * MIN
    period_ends = [p1, p1 + (45 + stoppage[1]) * MIN]
    meta = MatchMeta(
        match_id=match_id(seed),
        seed=seed,
        competition="Synthetic League",
        venue=venue,
        home=home.team,
        away=away.team,
        players=home.players + away.players,
        period_end_ms=period_ends,
    )
    mods = storylines.plan(rs.storylines, home, away, period_ends, control)
    result = Engine(meta, home, away, mods, rs.engine, rs.noise).run()
    result.timings["simulate_s"] = time.perf_counter() - t0
    return result, storylines.ground_truth(meta.match_id, seed, control, mods)
