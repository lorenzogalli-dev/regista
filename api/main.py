"""FastAPI entry point."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from api import data_sync, db, telemetry
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
    telemetry.setup()
    data_sync.sync()
    await db.apply_schema()
    server = build_server(registry)
    mcp_mount.app = server.streamable_http_app()
    async with server.session_manager.run():
        yield


app = FastAPI(title="Regista", version="0.1.0", lifespan=lifespan)
app.include_router(replay.router)
app.include_router(runs.router)
# Metrics tools for agents over MCP (streamable HTTP) at /mcp/
app.mount("/mcp", mcp_mount)


@app.get("/health")
async def health(db_ok: Annotated[bool, Depends(db.ping)]) -> JSONResponse:
    body = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "unreachable"}
    return JSONResponse(body, status_code=200 if db_ok else 503)


SPA_ROUTES = {
    "",
    "broadcast",
    "split",
    "control",
    "graphics",
    "eval",
    "second",
    "recap",
    "architecture",
    "design",
    "tour",
}


class _SpaFiles(StaticFiles):
    """The built front-end: real files when they exist, otherwise index.html (client routes)."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            # Only the front-end's own routes fall back to the app shell; anything else is 404.
            if e.status_code != 404 or path.split("/")[0] not in SPA_ROUTES:
                raise
            return await super().get_response("index.html", scope)


WEB_DIST = Path(os.environ.get("WEB_DIST", "web/dist"))
if (WEB_DIST / "index.html").is_file():
    # Registered last: API, WebSocket and MCP routes take precedence.
    app.mount("/", _SpaFiles(directory=WEB_DIST, html=True), name="web")
