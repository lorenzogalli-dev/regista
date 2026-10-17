import asyncio
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mcp.shared.memory import create_connected_server_and_client_session

from metrics.mcp_server import StoreRegistry, build_server

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "get_match_info",
    "get_window_stats",
    "compare_windows",
    "get_player_physical",
    "get_sequence",
    "get_moment_context",
}
# Modules that run in the agent / API process. None may know where the ground truth lives.
RUNTIME_MODULES = [
    *sorted((ROOT / "api").rglob("*.py")),
    *sorted((ROOT / "agents").rglob("*.py")),
    ROOT / "metrics" / "store.py",
    ROOT / "metrics" / "tools.py",
    ROOT / "metrics" / "mcp_server.py",
    ROOT / "metrics" / "counters.py",
    ROOT / "metrics" / "models.py",
    ROOT / "metrics" / "control.py",
]
FORBIDDEN = re.compile(
    r"ground_truth|GROUND_TRUTH|storylines|signal_check|from eval|import eval|sim\.generate"
)


def _call_all(registry: StoreRegistry, match_id: str, team: str, player: str) -> dict[str, str]:
    server = build_server(registry)

    async def run() -> dict[str, str]:
        out = {}
        async with create_connected_server_and_client_session(server._mcp_server) as client:
            tools = (await client.list_tools()).tools
            out["__list__"] = json.dumps([t.model_dump() for t in tools])
            calls = {
                "get_match_info": {"match_id": match_id},
                "get_window_stats": {
                    "match_id": match_id,
                    "team_id": team,
                    "start_ms": 0,
                    "end_ms": 10**7,
                },
                "compare_windows": {
                    "match_id": match_id,
                    "team_id": team,
                    "before_start_ms": 0,
                    "before_end_ms": 1_800_000,
                    "after_start_ms": 1_800_000,
                    "after_end_ms": 3_600_000,
                },
                "get_player_physical": {
                    "match_id": match_id,
                    "player_id": player,
                    "start_ms": 0,
                    "end_ms": 10**7,
                },
                "get_sequence": {"match_id": match_id, "possession_id": 10},
                "get_moment_context": {"match_id": match_id, "t_ms": 3_000_000},
            }
            for name, args in calls.items():
                res = await client.call_tool(name, args)
                assert not res.isError, (name, res.content)
                out[name] = json.dumps(res.structuredContent)
            bad = await client.call_tool(
                "get_window_stats",
                {"match_id": "../ground_truth", "team_id": team, "start_ms": 0, "end_ms": 1},
            )
            assert bad.isError
        return out

    return asyncio.run(run())


@pytest.fixture(scope="module")
def responses(sample_dirs, sample) -> dict[str, str]:
    out, _ = sample_dirs
    meta = sample[0].meta
    return _call_all(
        StoreRegistry(out.parent), meta.match_id, meta.home.team_id, meta.players[5].player_id
    )


def test_tools_listed_with_safe_schemas(responses) -> None:
    tools = json.loads(responses["__list__"])
    assert {t["name"] for t in tools} == EXPECTED_TOOLS
    for t in tools:
        props = t["inputSchema"]["properties"]
        for name, schema in props.items():
            assert not re.search(r"path|file|dir|url", name), (t["name"], name)
            if schema.get("type") == "string":
                assert "pattern" in schema, (t["name"], name)
            else:
                assert schema.get("type") == "integer", (t["name"], name, schema)


def test_tool_outputs_never_contain_ground_truth(responses, sample) -> None:
    _, gt = sample
    blob = "\n".join(v for k, v in responses.items() if k != "__list__")
    assert "storyline" not in blob.lower()
    for sl in gt.storylines:
        assert sl.canonical_explanation not in blob
        assert sl.storyline_id not in blob and "expected_signals" not in blob


def test_tool_values_match_direct_tools(responses, sample_dirs, sample) -> None:
    from metrics.tools import MatchTools

    reg = StoreRegistry(sample_dirs[0].parent)
    direct = MatchTools(reg.tools(sample[0].meta.match_id).store)
    ws = direct.get_window_stats(sample[0].meta.home.team_id, 0, 10**7)
    assert json.loads(responses["get_window_stats"]) == json.loads(ws.model_dump_json())


def test_runtime_modules_do_not_reference_ground_truth() -> None:
    for path in RUNTIME_MODULES:
        text = path.read_text()
        assert not FORBIDDEN.search(text), path


def test_mcp_over_http_through_api(sample_dirs, monkeypatch) -> None:
    from api import main

    monkeypatch.setattr(main.registry, "data_dir", sample_dirs[0].parent)
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "testserver")
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(main.app) as client:
        init = client.post(
            "/mcp/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        assert init.status_code == 200, init.text
        r = client.post(
            "/mcp/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_moment_context",
                    "arguments": {"match_id": "m_1000", "t_ms": 600_000},
                },
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["result"]["structuredContent"]["clock"] == "10:00"
