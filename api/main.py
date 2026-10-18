"""FastAPI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from api import db
from api.routes import replay, runs
from metrics.mcp_server import StoreRegistry, build_server

registry = StoreRegistry()


class _McpMount:
    """ASGI shim: an MCP session manager runs once, so each app lifespan builds a fresh one."""

    app: ASGIApp | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.app is None:
            raise RuntimeError("MCP server not started")
        await self.app(scope, receive, send)


mcp_mount = _McpMount()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.apply_schema()
    server = build_server(registry)
    mcp_mount.app = server.streamable_http_app()
    async with server.session_manager.run():
        yield


app = FastAPI(title="Ground Truth Football", version="0.1.0", lifespan=lifespan)
app.include_router(replay.router)
app.include_router(runs.router)
# Metrics tools for agents over MCP (streamable HTTP) at /mcp/
app.mount("/mcp", mcp_mount)


@app.get("/health")
async def health(db_ok: Annotated[bool, Depends(db.ping)]) -> JSONResponse:
    body = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "unreachable"}
    return JSONResponse(body, status_code=200 if db_ok else 503)
