"""Plausibility summary of simulated matches (SPEC §4 targets)."""

from dataclasses import asdict, dataclass

import numpy as np

from sim.engine import SimResult


@dataclass(frozen=True)
class Summary:
    seed: int
    passes: int
    pass_completion: float
    shots: int
    goals: int
    max_player_speed: float
    tackles: int
    possession_changes: int

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def summarise(result: SimResult) -> Summary:
    ev = result.events
    passes = [e for e in ev if e["type"] == "pass"]
    complete = sum(e["outcome"] == "complete" for e in passes)
    return Summary(
        seed=result.meta.seed,
        passes=len(passes),
        pass_completion=complete / max(1, len(passes)),
        shots=sum(e["type"] == "shot" for e in ev),
        goals=sum(e["type"] == "goal" for e in ev),
        max_player_speed=float(np.max(result.speed)),
        tackles=sum(e["type"] == "tackle" for e in ev),
        possession_changes=sum(e["type"] == "possession_change" for e in ev),
    )


def _one(seed: int) -> Summary:
    from sim.generate import simulate

    return summarise(simulate(seed)[0])


def summarise_seeds(seeds: list[int], workers: int = 4) -> list[Summary]:
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, seeds))
