"""Cost estimate for a Foundry run, before spending anything.

Runs the real pipeline with the fake client on the same matches: input tokens come from the
actual prompts (instructions, payloads, tool schemas, tool round trips; chars / 4), output
tokens from per-agent assumptions for real models, including reasoning tokens for the Analyst.
Prices come from env (`PRICE_*_EUR_PER_M`, see agents.config). The result is a range.

    uv run python -m agents.estimate m_1000 m_1001 --mode full
"""

import argparse
import asyncio
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from agents.config import Settings
from agents.run import run_match

# Output tokens per call for real models (visible text + reasoning), per agent. An Analyst
# attempt is usually two calls (a tool call, then the answer): ~1800 tokens per attempt.
OUTPUT_TOKENS = {
    "detector": 150,
    "analyst": 900,
    "verifier": 150,
    "narrator": 80,
    "persona": 2000,
    "director": 60,
}
RETRY_SHARE = 0.25  # share of explanations a real Verifier sends back once
INPUT_MARGIN = 1.15  # chars / 4 undercounts some tokenisers
RANGE = (0.7, 1.5)


def estimate(runs: list[dict[str, Any]], settings: Settings) -> dict[str, Any]:
    p = settings.prices
    per_agent: dict[str, dict[str, float]] = {}
    for run in runs:
        for c in run["calls"]:
            a = per_agent.setdefault(c["agent"], {"calls": 0, "tokens_in": 0, "tokens_out": 0})
            a["calls"] += 1
            a["tokens_in"] += c["tokens_in"] * INPUT_MARGIN
            a["tokens_out"] += OUTPUT_TOKENS.get(c["agent"], 200)
    if "analyst" in per_agent:
        for k in ("calls", "tokens_in", "tokens_out"):
            per_agent["analyst"][k] *= 1 + RETRY_SHARE
    total = 0.0
    for name, a in per_agent.items():
        role = "reasoning" if name == "analyst" else "fast"
        a["eur"] = p.cost(role, int(a["tokens_in"]), int(a["tokens_out"]))  # type: ignore[arg-type]
        total += a["eur"]
    return {
        "matches": [r["match_id"] for r in runs],
        "candidates": sum(r["candidates"] for r in runs),
        "per_agent": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in per_agent.items()},
        "eur_point": round(total, 3),
        "eur_range": [round(total * RANGE[0], 3), round(total * RANGE[1], 3)],
        "prices_eur_per_m": vars(p),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agents.estimate")
    ap.add_argument("match_ids", nargs="+")
    ap.add_argument("--mode", choices=["full", "eval"], default="full")
    a = ap.parse_args(argv)
    data_dir = Path(os.environ.get("MATCH_DATA_DIR", "data/generated"))
    settings = replace(Settings(), provider="fake", run_budget_eur=1e9)

    async def all_runs() -> list[dict[str, Any]]:
        return [await run_match(data_dir / m, a.mode, settings) for m in a.match_ids]

    est = estimate(asyncio.run(all_runs()), settings)
    print(json.dumps(est, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
