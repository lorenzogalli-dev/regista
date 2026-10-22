"""Replay a generated match as a paced, time-ordered stream of events and tracking frames."""

import asyncio
import contextlib
import heapq
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

from sim import io

Message = dict[str, Any]


def frame_stride(speed: float) -> int:
    """Tracking frames to skip so the stream stays near 10-20 frames per wall second.

    1x -> every frame (10 Hz), 4x -> every 2nd, 20x -> every 10th. Clients interpolate.
    """
    return max(1, round(speed / 2))


def merged(match_dir: Path, speed: float, from_ms: int = 0) -> Iterator[Message]:
    """Events and (decimated) frames merged by t_ms; at equal t_ms events come first."""
    stride = frame_stride(speed)
    events = (
        (e["t_ms"], 0, i, {"type": "event", "data": e})
        for i, e in enumerate(io.iter_events(match_dir))
        if e["t_ms"] >= from_ms
    )
    frames = (
        (f["t_ms"], 1, i, {"type": "frame", "data": f})
        for i, f in enumerate(io.iter_tracking(match_dir, from_ms))
        if (f["t_ms"] // 100) % stride == 0
    )
    for _, _, _, msg in heapq.merge(events, frames):
        yield msg


class Pace:
    """A playback rate a client can change mid-stream (0 holds the stream)."""

    def __init__(self, speed: float) -> None:
        self.speed = speed
        self.changed = asyncio.Event()

    def set(self, speed: float) -> None:
        self.speed = speed
        self.changed.set()

    async def wait(self, timeout: float | None) -> None:
        """Sleep until `timeout` elapses or the rate changes."""
        self.changed.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.changed.wait(), timeout)


async def replay(
    match_dir: Path,
    speed: float = 1.0,
    from_ms: int = 0,
    *,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    pace: Pace | None = None,
) -> AsyncIterator[Message]:
    """Yield messages paced so that match time advances `speed` times faster than wall time.

    With `pace`, the rate follows `pace.speed` as it changes (frame decimation stays as for
    the starting `speed`).
    """
    if speed <= 0:
        raise ValueError("speed must be positive")
    meta = io.read_meta(match_dir)
    yield {"type": "meta", "data": meta.model_dump(), "speed": speed, "from_ms": from_ms}
    anchor_t, anchor_wall, rate = float(from_ms), now(), speed
    for msg in merged(match_dir, speed, from_ms):
        t = msg["data"]["t_ms"]
        while True:
            if pace is not None and pace.speed != rate:
                # Re-anchor at the match time reached so far at the old rate.
                wall = now()
                anchor_t = min(float(t), anchor_t + (wall - anchor_wall) * rate * 1000.0)
                anchor_wall, rate = wall, pace.speed
            if rate <= 0:
                await pace.wait(None)  # type: ignore[union-attr]
                continue
            wait = (t - anchor_t) / 1000.0 / rate - (now() - anchor_wall)
            if wait <= 0:
                break
            if pace is None:
                await sleep(wait)
                break
            await pace.wait(wait)
        yield msg
    yield {"type": "end"}
