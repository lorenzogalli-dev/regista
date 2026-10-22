"""Streams for the front-end: recorded agent runs and live sessions, one message vocabulary.

Messages: `meta`, `run` (header: recorded or live), `frame`, `event`, `overlay` (SPEC §6.2),
`pipeline` (stage start/end and verdicts, for the control room), `notice`, `end`.

- Recorded: the match replay merged with the run's saved overlays and pipeline events, at the
  latencies measured when the run was produced. Zero model calls.
- Live: the match is replayed into a live store; tier-0 overlays come straight from code;
  candidates go through the agent workflow in background tasks (the stream never waits for
  them); tier-1 cards appear as a template when the Detector keeps a moment and are replaced
  by the verified text or withdrawn. Model calls are capped per UTC day.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents.candidates import Candidate, CandidateFinder
from agents.config import Settings
from agents.overlays import Tier0Feed, moment_overlays, overlay, pipeline_events, template_card
from agents.pipeline import Desk, MomentWork, run_moment
from agents.providers import Meter
from metrics.store import MatchStore
from metrics.tools import MatchTools
from sim import io
from sim.replay import Pace, replay

Message = dict[str, Any]
CAP_NOTICE = (
    "Today's live model-call cap is reached: AI cards are paused; recorded runs remain available."
)
Send = Callable[[Message], Awaitable[None]]


def runs_dir() -> Path:
    return Path(os.environ.get("RUNS_DIR", "data/recorded"))


def load_run(run_id: str) -> dict[str, Any] | None:
    p = runs_dir() / f"{run_id}.json"
    if not p.is_file():
        return None
    data: dict[str, Any] = json.loads(p.read_text())
    return data


def run_header(run: dict[str, Any], kind: str) -> Message:
    return {
        "type": "run",
        "data": {
            "kind": kind,
            "run_id": run.get("run_id"),
            "match_id": run.get("match_id"),
            "models": run.get("models"),
            "provider": run.get("provider"),
            "usage": {k: run.get("usage", {}).get(k) for k in ("calls", "cost_eur")},
            "provenance": run.get("provenance"),
            "featured_rejection": run.get("featured_rejection"),
        },
    }


def timeline(run: dict[str, Any]) -> list[tuple[int, Message]]:
    items: list[tuple[int, Message]] = [
        (o["show_at_ms"], {"type": "overlay", "data": o}) for o in run.get("overlays", [])
    ]
    for m in run.get("moments", []):
        items += [(e["at_ms"], e) for e in pipeline_events(m)]
    items.sort(key=lambda x: x[0])
    return items


async def recorded_stream(
    run: dict[str, Any], match_dir: Path, speed: float, from_ms: int = 0, pace: Pace | None = None
) -> AsyncIterator[Message]:
    yield run_header(run, "Recorded agent run")
    if from_ms > 0:
        # Joining mid-match: the history the graphics need (score, possession, ribbon).
        yield {"type": "meta", "data": io.read_meta(match_dir).model_dump()}
        # One message for all earlier events: thousands of single messages delay the first frame.
        history = []
        for e in io.iter_events(match_dir):
            if e["t_ms"] >= from_ms:
                break
            history.append(e)
        yield {"type": "events", "data": history}
        for t, m in timeline(run):
            if t >= from_ms or m["type"] != "overlay":
                continue
            o = m["data"]
            if o["kind"] == "momentum_bar" or o["show_at_ms"] + o["duration_ms"] > from_ms:
                yield m  # ribbon history and graphics still on air
    items = [it for it in timeline(run) if it[0] >= from_ms]
    i = 0
    async for msg in replay(match_dir, speed, from_ms, pace=pace):
        now = msg.get("data", {}).get("t_ms") if msg["type"] in ("frame", "event") else None
        if now is not None:
            while i < len(items) and items[i][0] <= now:
                yield items[i][1]
                i += 1
        if msg["type"] == "end":
            for _, m in items[i:]:
                yield m
        yield msg


class DailyCap:
    """Model calls per UTC day for live sessions (one process; resets at midnight UTC)."""

    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.day = ""
        self.used = 0

    def _roll(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        if today != self.day:
            self.day, self.used = today, 0

    def remaining(self) -> int:
        self._roll()
        return max(0, self.cap - self.used)

    def add(self, n: int) -> None:
        self._roll()
        self.used += n


DAILY_CAP = DailyCap(int(os.environ.get("LIVE_DAILY_MODEL_CALL_CAP", "2000")))


async def live_session(
    match_dir: Path,
    speed: float,
    send: Send,
    settings: Settings | None = None,
    cap: DailyCap = DAILY_CAP,
    use_mcp: bool = True,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Run a live session and push messages through `send` until the match ends."""
    settings = settings or Settings()
    store = MatchStore(io.read_meta(match_dir))
    tools = MatchTools(store)
    meter = Meter(settings)
    finder = CandidateFinder(store)
    feed = Tier0Feed(store)
    lock = asyncio.Lock()
    tasks: set[asyncio.Task[None]] = set()

    async def out(msg: Message) -> None:
        async with lock:
            await send(msg)

    await out(
        run_header(
            {
                "match_id": store.meta.match_id,
                "provider": settings.provider,
                "models": {"fast": settings.model_fast, "reasoning": settings.model_reasoning},
            },
            "Live",
        )
    )
    with ExitStack() as stack:
        async with AsyncExitStack() as astack:
            analyst_tools = []
            if use_mcp:
                from agents.mcp_local import analyst_tool, serve

                tool = analyst_tool(stack.enter_context(serve(store)))
                analyst_tools = [await astack.enter_async_context(tool)]
            desk = Desk(settings, meter, tools, analyst_tools)

            async def process(c: Candidate) -> None:
                player = next(
                    (p.name for p in store.meta.players if p.player_id == c.player_id), None
                )
                template = template_card(c, desk.team_name(c.team_id), player, tools)
                shown = False
                calls_before = len(meter.calls)

                def listener(ev: Message) -> None:
                    nonlocal shown
                    ev = {**ev, "at_ms": store.now_ms}
                    pending = [asyncio.ensure_future(out(ev))]
                    if ev["stage"] == "analyst#1" and ev["phase"] == "start" and not shown:
                        shown = True
                        pending.append(
                            asyncio.ensure_future(
                                out(
                                    {
                                        "type": "overlay",
                                        "data": overlay(
                                            f"{c.candidate_id.replace('c_', 'mo_')}_t",
                                            "moment_card",
                                            store.now_ms,
                                            15_000,
                                            {**template, "state": "pending"},
                                            priority=2,
                                            source=c.candidate_id.replace("c_", "mo_"),
                                            tier=1,
                                        ),
                                    }
                                )
                            )
                        )
                    for p in pending:
                        tasks.add(p)
                        p.add_done_callback(tasks.discard)

                try:
                    w: MomentWork = await run_moment(desk, c, "full", listener)
                except Exception as e:  # a failed moment never stops the stream
                    await out({"type": "notice", "detail": f"moment {c.candidate_id} failed: {e}"})
                    return
                finally:
                    cap.add(len(meter.calls) - calls_before)
                for o in moment_overlays(w.to_dict(), template):
                    if o["payload"].get("state") == "pending":
                        continue
                    o["show_at_ms"] = store.now_ms
                    await out({"type": "overlay", "data": o})

            async for msg in replay(match_dir, speed, sleep=sleep):
                if msg["type"] == "frame":
                    store.ingest_frame(msg["data"])
                elif msg["type"] == "event":
                    store.ingest_event(msg["data"])
                await out(msg)
                if msg["type"] == "frame":
                    for o in feed.poll():
                        await out({"type": "overlay", "data": o})
                if store.now_ms >= finder.next_check:
                    for c in finder.poll():
                        if cap.remaining() <= 0:
                            await out(
                                {
                                    "type": "notice",
                                    "detail": CAP_NOTICE,
                                }
                            )
                            continue
                        t = asyncio.create_task(process(c))
                        tasks.add(t)
                        t.add_done_callback(tasks.discard)
            if tasks:
                await asyncio.gather(*list(tasks), return_exceptions=True)
