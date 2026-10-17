"""FastAPI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from api import db
from api.routes import replay


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.apply_schema()
    yield


app = FastAPI(title="Ground Truth Football", version="0.1.0", lifespan=lifespan)
app.include_router(replay.router)


@app.get("/health")
async def health(db_ok: Annotated[bool, Depends(db.ping)]) -> JSONResponse:
    body = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "unreachable"}
    return JSONResponse(body, status_code=200 if db_ok else 503)
