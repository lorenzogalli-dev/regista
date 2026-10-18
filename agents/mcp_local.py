"""Serve the metrics MCP server in-process for a run, over the run's live store.

The Analyst reaches the tools through Agent Framework's MCP client over streamable HTTP, the
same path the API exposes at /mcp/. The store only holds data ingested so far, so tool results
can never include the future.
"""

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from agent_framework import MCPStreamableHTTPTool
from starlette.applications import Starlette
from starlette.routing import Mount

from metrics.mcp_server import StoreRegistry, build_server
from metrics.store import MatchStore


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def serve(store: MatchStore) -> Iterator[str]:
    """Yield the URL of an MCP server whose registry holds `store`."""
    registry = StoreRegistry()
    registry.register(store)
    mcp = build_server(registry)
    inner = mcp.streamable_http_app()
    app = Starlette(routes=[Mount("/mcp", app=inner)], lifespan=lambda _: mcp.session_manager.run())
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}/mcp/"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def analyst_tool(url: str) -> MCPStreamableHTTPTool:
    """The metrics tools the Analyst may call (read-only, no paths)."""
    return MCPStreamableHTTPTool(
        name="metrics",
        url=url,
        load_prompts=False,
        approval_mode="never_require",
        allowed_tools=[
            "get_window_stats",
            "compare_windows",
            "get_player_physical",
            "get_sequence",
        ],
    )
