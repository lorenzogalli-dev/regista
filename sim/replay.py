"""Replay a generated match as a paced, time-ordered stream of events and tracking frames."""

import asyncio
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
        for i, f in enumerate(io.iter_tracking(match_dir))
        if f["t_ms"] >= from_ms and (f["t_ms"] // 100) % stride == 0
    )
    for _, _, _, msg in heapq.merge(events, frames):
        yield msg


async def replay(
    match_dir: Path,
    speed: float = 1.0,
    from_ms: int = 0,
    *,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncIterator[Message]:
    """Yield messages paced so that match time advances `speed` times faster than wall time."""
    if speed <= 0:
        raise ValueError("speed must be positive")
    meta = io.read_meta(match_dir)
    yield {"type": "meta", "data": meta.model_dump(), "speed": speed, "from_ms": from_ms}
    start = now()
    for msg in merged(match_dir, speed, from_ms):
        due = (msg["data"]["t_ms"] - from_ms) / 1000.0 / speed
        wait = due - (now() - start)
        if wait > 0:
            await sleep(wait)
        yield msg
    yield {"type": "end"}
