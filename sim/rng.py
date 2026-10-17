"""Independent random streams derived from one match seed.

Each subsystem draws from its own stream, so changing how often one subsystem draws
does not shift the numbers seen by the others.
"""

from dataclasses import dataclass

import numpy as np

_STREAMS = ("roster", "storylines", "engine", "noise")


@dataclass(frozen=True)
class Streams:
    roster: np.random.Generator
    storylines: np.random.Generator
    engine: np.random.Generator
    noise: np.random.Generator


def streams(seed: int) -> Streams:
    children = np.random.SeedSequence(seed).spawn(len(_STREAMS))
    gens = {
        name: np.random.Generator(np.random.PCG64(c))
        for name, c in zip(_STREAMS, children, strict=True)
    }
    return Streams(**gens)
