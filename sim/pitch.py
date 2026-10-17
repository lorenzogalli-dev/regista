"""Pitch geometry and the attacking-frame transform.

Absolute frame: 105 x 68 m, origin bottom-left. The attacking frame rotates the pitch
by 180 degrees for a team attacking towards x = 0, so every team attacks left to right
and its left flank stays its left flank.
"""

import math

from sim.schema import PITCH_LENGTH, PITCH_WIDTH

GOAL_HALF_WIDTH = 3.66


def direction(is_home: bool, period: int) -> int:
    """+1 if the team attacks towards x = 105 in this period, else -1."""
    home_up = period == 1
    return 1 if is_home == home_up else -1


def to_attacking(x: float, y: float, d: int) -> tuple[float, float]:
    return (x, y) if d == 1 else (PITCH_LENGTH - x, PITCH_WIDTH - y)


def from_attacking(ax: float, ay: float, d: int) -> tuple[float, float]:
    return to_attacking(ax, ay, d)


def goal_distance_angle(ax: float, ay: float) -> tuple[float, float]:
    """Distance (m) to the attacked goal's centre and the goal mouth's opening angle (rad)."""
    dx = PITCH_LENGTH - ax
    dy = ay - PITCH_WIDTH / 2
    dist = math.hypot(dx, dy)
    a1 = math.atan2(dy - GOAL_HALF_WIDTH, dx)
    a2 = math.atan2(dy + GOAL_HALF_WIDTH, dx)
    return dist, abs(a2 - a1)


def zone(ax: float, ay: float, cols: int = 6, rows: int = 4) -> tuple[int, int]:
    c = min(cols - 1, max(0, int(ax / PITCH_LENGTH * cols)))
    r = min(rows - 1, max(0, int(ay / PITCH_WIDTH * rows)))
    return c, r
