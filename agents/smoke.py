"""One minimal structured-output call per model role, to check auth, SDK and usage reporting.

uv run --env-file .env python -m agents.smoke   (MODEL_PROVIDER=foundry)
"""

import asyncio
import json
from dataclasses import replace
from typing import Any, cast

from agent_framework import Agent

from agents import ledger
from agents.config import Role, Settings
from agents.providers import Meter, make_client, metered, role_options
from agents.schemas import Caption


async def main() -> int:
    settings = replace(Settings(), provider="foundry")
    meter = Meter(settings, prior_eur=ledger.spent())
    out: list[dict[str, Any]] = []
    for role in cast(list[Role], ["fast", "reasoning"]):
        agent = Agent(
            client=make_client(settings, role),
            name=f"smoke-{role}",
            instructions="Reply with a caption of at most five words.",
            middleware=[metered(meter, f"smoke-{role}", role)],
        )
        opts = {"response_format": Caption, **role_options(settings, role)}
        res = await agent.run("Caption for: a quiet first half.", options=cast(Any, opts))
        c = meter.calls[-1]
        out.append(
            {
                "deployment": settings.model(role),
                "text": res.value.text if res.value else None,
                **vars(c),
            }
        )
    ledger.record(
        {
            "what": "smoke test",
            "provider": "foundry",
            "calls": len(meter.calls),
            "cost_eur": round(meter.spent_eur, 6),
        }
    )
    print(json.dumps(out, indent=1))
    print(f"total {meter.spent_eur:.6f} EUR; ledger {ledger.spent():.6f} EUR")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
