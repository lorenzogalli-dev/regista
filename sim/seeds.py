"""Fixed seed sets. Tune the simulator and prompts on DEV only; EVAL is reserved for reporting."""

DEV_SEEDS: tuple[int, ...] = tuple(range(1000, 1020))
EVAL_SEEDS: tuple[int, ...] = tuple(range(5000, 5020))
CONTROL_SEEDS: tuple[int, ...] = tuple(range(9000, 9010))


def is_control(seed: int) -> bool:
    return seed in CONTROL_SEEDS
