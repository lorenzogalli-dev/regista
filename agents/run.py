"""Run the agent pipeline over a generated match (offline, as fast as the agents allow).

    uv run python -m agents.run m_1000 [--mode full|eval] [--no-mcp] [--out data/runs]

The match is replayed in time order into a live store. Candidates are checked every minute of
match time; each candidate goes through the workflow before ingestion continues, so agents and
tools only ever see data up to the candidate's time. The run (moments, verdicts, overlays,
token usage, cost) is saved as JSON; recorded agent runs are these real outputs, replayed later
with zero model calls.

Reads only public match data from MATCH_DATA_DIR; never the ground-truth directory.
"""

import argparse
import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import AsyncExitStack, ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from agents import ledger
from agents.candidates import CandidateFinder
from agents.config import Settings
from agents.pipeline import Desk, MomentWork, run_moment
from agents.providers import BudgetExceeded, Meter
from metrics.store import MatchStore
from metrics.tools import MatchTools
from sim import io
from sim.replay import merged


async def run_match(
    match_dir: Path,
    mode: Literal["full", "eval"] = "full",
    settings: Settings | None = None,
    use_mcp: bool = True,
) -> dict[str, Any]:
    settings = settings or Settings()
    store = MatchStore(io.read_meta(match_dir))
    tools = MatchTools(store)
    meter = Meter(settings)
    if settings.provider != "fake":
        meter.prior_eur = ledger.spent()
    finder = CandidateFinder(store)
    moments: list[MomentWork] = []
    stopped: str | None = None
    t0 = time.perf_counter()
    started = datetime.now(UTC).isoformat()

    with ExitStack() as stack:
        analyst_tools = []
        tool_stack = AsyncExitStack()
        if use_mcp:
            from agents.mcp_local import analyst_tool, serve

            # Connect in this task so the MCP client session also closes in it.
            tool = analyst_tool(stack.enter_context(serve(store)))
            analyst_tools = [await tool_stack.enter_async_context(tool)]
        desk = Desk(settings, meter, tools, analyst_tools)
        for m in merged(match_dir, speed=1.0):
            if m["type"] == "frame":
                store.ingest_frame(m["data"])
            else:
                store.ingest_event(m["data"])
            if store.now_ms < finder.next_check or stopped:
                continue
            for c in finder.poll():
                try:
                    moments.append(await run_moment(desk, c, mode))
                except BudgetExceeded as e:
                    stopped = str(e)
                    break
                except Exception as e:  # the workflow wraps executor errors
                    if isinstance(e.__cause__, BudgetExceeded) or "budget" in str(e):
                        stopped = str(e)
                        break
                    raise
        await tool_stack.aclose()

    if settings.provider != "fake":
        ledger.record(
            {
                "what": f"run {store.meta.match_id} {mode}",
                "provider": settings.provider,
                "calls": len(meter.calls),
                "cost_eur": round(meter.spent_eur, 6),
            }
        )

    counts: dict[str, int] = {}
    for w in moments:
        counts[w.status] = counts.get(w.status, 0) + 1
    return {
        "run_id": f"r_{store.meta.match_id}_{uuid.uuid4().hex[:8]}",
        "match_id": store.meta.match_id,
        "mode": mode,
        "kind": "recorded agent run",
        "provider": settings.provider,
        "models": {
            "fast": settings.model_fast,
            "reasoning": settings.model_reasoning,
            "reasoning_effort": settings.reasoning_effort,
        },
        "started_at": started,
        "wall_s": round(time.perf_counter() - t0, 1),
        "candidates": finder.count,
        "status_counts": counts,
        "budget_stopped": stopped,
        "usage": meter.summary(),
        "calls": [vars(c) for c in meter.calls],
        "moments": [w.to_dict() for w in moments],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agents.run")
    ap.add_argument("match_id")
    ap.add_argument("--mode", choices=["full", "eval"], default="full")
    ap.add_argument("--no-mcp", action="store_true", help="Analyst without tool calls")
    ap.add_argument("--out", type=Path, default=Path("data/runs"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    data_dir = Path(os.environ.get("MATCH_DATA_DIR", "data/generated"))
    run = asyncio.run(run_match(data_dir / a.match_id, a.mode, use_mcp=not a.no_mcp))
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False) + "\n")
    if url := os.environ.get("DATABASE_URL"):
        from agents.persist import save_run

        try:
            save_run(url, run)
        except Exception as e:  # the JSON file is the record; the database is a copy
            logging.warning("run not saved to the database: %s", e)
    u = run["usage"]
    print(
        f"{path}: {run['candidates']} candidates, {run['status_counts']}, "
        f"{u['calls']} model calls, {u['tokens_in']} in / {u['tokens_out']} out tokens"
        f"{' (estimated)' if u['estimated'] else ''}, {u['cost_eur']:.4f} EUR, {run['wall_s']} s"
    )
    if run["budget_stopped"]:
        print(f"STOPPED: {run['budget_stopped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
