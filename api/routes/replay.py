"""Match listing and replay streaming. Reads only MATCH_DATA_DIR (never the ground truth)."""

import os
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from sim import io
from sim.replay import replay

router = APIRouter()
MATCH_ID = re.compile(r"^m_\d{1,9}$")


def data_dir() -> Path:
    return Path(os.environ.get("MATCH_DATA_DIR", "data/generated"))


def _match_dir(match_id: str) -> Path | None:
    if not MATCH_ID.match(match_id):
        return None
    d = data_dir() / match_id
    return d if (d / io.MATCH_FILE).is_file() else None


@router.get("/api/matches")
def list_matches() -> list[dict[str, Any]]:
    root = data_dir()
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if MATCH_ID.match(d.name) and (d / io.MATCH_FILE).is_file():
            m = io.read_meta(d)
            out.append(
                {
                    "match_id": m.match_id,
                    "seed": m.seed,
                    "venue": m.venue,
                    "home": m.home.name,
                    "away": m.away.name,
                    "duration_ms": m.period_end_ms[-1],
                }
            )
    return out


@router.get("/api/matches/{match_id}")
def get_match(match_id: str) -> dict[str, Any]:
    d = _match_dir(match_id)
    if d is None:
        raise HTTPException(404, "match not found")
    return io.read_meta(d).model_dump()


@router.websocket("/ws/replay/{match_id}")
async def ws_replay(
    ws: WebSocket,
    match_id: str,
    speed: Annotated[float, Query(gt=0, le=100)] = 1.0,
    from_ms: Annotated[int, Query(ge=0)] = 0,
) -> None:
    d = _match_dir(match_id)
    await ws.accept()
    if d is None:
        await ws.send_json({"type": "error", "detail": "match not found"})
        await ws.close(code=4404)
        return
    try:
        async for msg in replay(d, speed, from_ms):
            await ws.send_json(msg)
        await ws.close()
    except WebSocketDisconnect:
        return
