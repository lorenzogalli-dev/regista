"""Fixed seed sets. Tune the simulator and prompts on DEV only; EVAL is reserved for reporting."""

DEV_SEEDS: tuple[int, ...] = tuple(range(1000, 1020))
EVAL_SEEDS: tuple[int, ...] = tuple(range(5000, 5020))
CONTROL_SEEDS: tuple[int, ...] = tuple(range(9000, 9010))

# Simulator calibration and model fitting (xG, xT, pass difficulty). Never used for reporting.
CALIBRATION_SEEDS: tuple[int, ...] = tuple(range(2000, 2200))
# Same, generated with zero storylines (noise reference for signal checks).
CALIBRATION_CONTROL_SEEDS: tuple[int, ...] = tuple(range(2200, 2300))


def is_control(seed: int) -> bool:
    return seed in CONTROL_SEEDS or seed in CALIBRATION_CONTROL_SEEDS
