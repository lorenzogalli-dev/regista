"""MCP server exposing the metrics tools (Model Context Protocol, streamable HTTP).

Agents reach numbers only through these tools. The server holds live `MatchStore`s in a
registry; it can also load a recorded match from MATCH_DATA_DIR (public events and
tracking only). It has no access to the ground-truth directory and no tool accepts a
path: every input is an id, a time or an integer.
"""

import os
import re
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

from metrics.store import MatchStore
from metrics.tools import (
    MatchInfo,
    MatchTools,
    MomentContext,
    Ms,
    PlayerId,
    PlayerPhysical,
    Sequence,
    TeamId,
    WindowComparison,
    WindowStats,
)
from sim import io
from sim.replay import merged

MATCH_ID_RE = re.compile(r"^m_\d{1,9}$")
MatchId = Annotated[str, Field(pattern=MATCH_ID_RE.pattern, description="match id, e.g. m_1000")]

INSTRUCTIONS = (
    "Deterministic football metrics over a synthetic match, computed from events and "
    "tracking ingested so far. Every number an analysis states must come from these tools. "
    "Times are ms since kickoff. Possession is time-based possession."
)


class StoreRegistry:
    """Live stores by match id; recorded matches load from MATCH_DATA_DIR on first use."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path(os.environ.get("MATCH_DATA_DIR", "data/generated"))
        self._stores: dict[str, MatchStore] = {}

    def register(self, store: MatchStore) -> None:
        self._stores[store.meta.match_id] = store

    def tools(self, match_id: str) -> MatchTools:
        if not MATCH_ID_RE.match(match_id):
            raise ValueError("invalid match id")
        if match_id not in self._stores:
            self._stores[match_id] = self._load_recorded(match_id)
        return MatchTools(self._stores[match_id])

    def _load_recorded(self, match_id: str) -> MatchStore:
        d = self.data_dir / match_id
        if not (d / io.MATCH_FILE).is_file():
            raise ValueError(f"unknown match {match_id}")
        st = MatchStore(io.read_meta(d))
        for m in merged(d, speed=1.0):
            if m["type"] == "frame":
                st.ingest_frame(m["data"])
            else:
                st.ingest_event(m["data"])
        return st


def allowed_hosts() -> list[str]:
    """Hosts accepted by the MCP endpoint (DNS-rebinding protection), from MCP_ALLOWED_HOSTS."""
    raw = os.environ.get("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*")
    return [h.strip() for h in raw.split(",") if h.strip()]


def build_server(registry: StoreRegistry) -> FastMCP:
    mcp = FastMCP(
        "regista-metrics",
        instructions=INSTRUCTIONS,
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=allowed_hosts()
        ),
    )

    @mcp.tool()
    def get_match_info(match_id: MatchId) -> MatchInfo:
        """Teams, players (ids, names, positions) and the latest ingested time."""
        return registry.tools(match_id).get_match_info()

    @mcp.tool()
    def get_window_stats(
        match_id: MatchId, team_id: TeamId, start_ms: Ms, end_ms: Ms
    ) -> WindowStats:
        """Team metrics over [start_ms, end_ms): time-based possession, field tilt, PPDA,
        pass completion, width, flank shares, shots, xG, xT added, control index."""
        return registry.tools(match_id).get_window_stats(team_id, start_ms, end_ms)

    @mcp.tool()
    def compare_windows(
        match_id: MatchId,
        team_id: TeamId,
        before_start_ms: Ms,
        before_end_ms: Ms,
        after_start_ms: Ms,
        after_end_ms: Ms,
    ) -> WindowComparison:
        """The same team metrics in two windows, with before, after and delta per metric."""
        return registry.tools(match_id).compare_windows(
            team_id, before_start_ms, before_end_ms, after_start_ms, after_end_ms
        )

    @mcp.tool()
    def get_player_physical(
        match_id: MatchId, player_id: PlayerId, start_ms: Ms, end_ms: Ms
    ) -> PlayerPhysical:
        """Distance, high-intensity distance, sprints, top speed, touches and passes."""
        return registry.tools(match_id).get_player_physical(player_id, start_ms, end_ms)

    @mcp.tool()
    def get_sequence(
        match_id: MatchId, possession_id: Annotated[int, Field(ge=0, le=100_000)]
    ) -> Sequence:
        """Events of one possession with pass cards (length, progression, difficulty), xG, xT."""
        return registry.tools(match_id).get_sequence(possession_id)

    @mcp.tool()
    def get_moment_context(match_id: MatchId, t_ms: Ms) -> MomentContext:
        """Clock, score, recent events and threshold triggers, last 5 and 15 minutes per team."""
        return registry.tools(match_id).get_moment_context(t_ms)

    return mcp
