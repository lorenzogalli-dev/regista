"""Recorded agent runs, the evaluation report and live sessions.

Recorded runs are real pipeline outputs saved as JSON in RUNS_DIR; replaying one makes zero
model calls. Live sessions run the agents and count against LIVE_DAILY_MODEL_CALL_CAP.
"""

import json
import os
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from agents import live
from api.routes.replay import _match_dir

router = APIRouter()
RUN_ID = re.compile(r"^r_m_\d{1,9}_[0-9a-f]{8}$")


def _run(run_id: str) -> dict[str, Any]:
    run = live.load_run(run_id) if RUN_ID.match(run_id) else None
    if run is None:
        raise HTTPException(404, "run not found")
    return run


@router.get("/api/runs")
def list_runs() -> list[dict[str, Any]]:
    root = live.runs_dir()
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.glob("r_m_*.json")):
        r = json.loads(p.read_text())
        out.append(
            {
                "run_id": r["run_id"],
                "match_id": r["match_id"],
                "kind": "Recorded agent run",
                "models": r.get("models"),
                "moments": len(r.get("moments", [])),
                "published": sum(m["status"] == "published" for m in r.get("moments", [])),
                "rejections": sum(
                    any(s["outcome"] == "rejected" for s in m["stages"])
                    for m in r.get("moments", [])
                ),
                "cost_eur": r.get("usage", {}).get("cost_eur"),
            }
        )
    return out


@router.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = _run(run_id)
    return {k: v for k, v in run.items() if k != "calls"}


@router.get("/api/eval/report")
def eval_report() -> dict[str, Any]:
    p = Path(os.environ.get("EVAL_REPORT", "docs/eval/report.json"))
    if not p.is_file():
        raise HTTPException(404, "no evaluation report")
    data: dict[str, Any] = json.loads(p.read_text())
    return data


@router.get("/api/live/quota")
def live_quota() -> dict[str, int]:
    return {"remaining": live.DAILY_CAP.remaining(), "cap": live.DAILY_CAP.cap}


@router.websocket("/ws/recorded/{run_id}")
async def ws_recorded(
    ws: WebSocket,
    run_id: str,
    speed: Annotated[float, Query(gt=0, le=100)] = 1.0,
    from_ms: Annotated[int, Query(ge=0)] = 0,
) -> None:
    await ws.accept()
    run = live.load_run(run_id) if RUN_ID.match(run_id) else None
    d = _match_dir(run["match_id"]) if run else None
    if run is None or d is None:
        await ws.send_json({"type": "error", "detail": "run not found"})
        await ws.close(code=4404)
        return
    try:
        async for msg in live.recorded_stream(run, d, speed, from_ms):
            await ws.send_json(msg)
        await ws.close()
    except WebSocketDisconnect:
        return


@router.websocket("/ws/live/{match_id}")
async def ws_live(
    ws: WebSocket, match_id: str, speed: Annotated[float, Query(gt=0, le=20)] = 1.0
) -> None:
    await ws.accept()
    d = _match_dir(match_id)
    if d is None:
        await ws.send_json({"type": "error", "detail": "match not found"})
        await ws.close(code=4404)
        return
    if live.DAILY_CAP.remaining() <= 0:
        await ws.send_json(
            {
                "type": "error",
                "detail": "Live sessions are paused: today's model-call cap is "
                "reached. Recorded agent runs are available.",
            }
        )
        await ws.close(code=4429)
        return
    try:
        await live.live_session(d, speed, ws.send_json)
        await ws.close()
    except WebSocketDisconnect:
        return
