"""Chat clients per provider, and the meter that counts tokens and enforces the run budget.

Every model call goes through `metered()` chat middleware: it refuses the call once the run's
estimated spend reaches `RUN_BUDGET_EUR` and records tokens, latency and cost per agent call.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from agent_framework import ChatContext, chat_middleware

from agents.config import Role, Settings


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Call:
    agent: str
    role: Role
    tokens_in: int
    tokens_out: int
    reasoning_tokens: int
    latency_ms: int
    cost_eur: float
    estimated: bool  # True when the provider reports no usage (fake): tokens are chars / 4


@dataclass
class Meter:
    settings: Settings
    calls: list[Call] = field(default_factory=list)
    prior_eur: float = 0.0  # spent by earlier runs (ledger), for the cumulative cap

    @property
    def spent_eur(self) -> float:
        return sum(c.cost_eur for c in self.calls)

    def summary(self) -> dict[str, Any]:
        by_agent: dict[str, dict[str, float]] = {}
        for c in self.calls:
            a = by_agent.setdefault(
                c.agent, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "eur": 0}
            )
            a["calls"] += 1
            a["tokens_in"] += c.tokens_in
            a["tokens_out"] += c.tokens_out
            a["eur"] += c.cost_eur
        return {
            "provider": self.settings.provider,
            "calls": len(self.calls),
            "tokens_in": sum(c.tokens_in for c in self.calls),
            "tokens_out": sum(c.tokens_out for c in self.calls),
            "cost_eur": round(self.spent_eur, 5),
            "estimated": any(c.estimated for c in self.calls),
            "by_agent": {k: {**v, "eur": round(v["eur"], 5)} for k, v in by_agent.items()},
        }


def _prompt_chars(context: ChatContext) -> int:
    """Characters sent: messages, instructions and tool schemas (for the chars / 4 estimate)."""
    opts = context.options or {}
    n = sum(len(getattr(m, "text", "") or "") for m in context.messages)
    n += len(str(opts.get("instructions") or ""))
    n += sum(len(str(getattr(t, "parameters", lambda: "")())) for t in opts.get("tools") or [])
    return n


def metered(meter: Meter, agent: str, role: Role) -> Callable[..., Awaitable[None]]:
    @chat_middleware
    async def middleware(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
        if meter.spent_eur >= meter.settings.run_budget_eur:
            raise BudgetExceeded(
                f"run budget {meter.settings.run_budget_eur} EUR reached "
                f"({meter.spent_eur:.4f} EUR spent); call to {agent} refused"
            )
        if meter.prior_eur + meter.spent_eur >= meter.settings.total_cap_eur:
            raise BudgetExceeded(
                f"cumulative cap {meter.settings.total_cap_eur} EUR reached "
                f"({meter.prior_eur + meter.spent_eur:.4f} EUR); call to {agent} refused"
            )
        t0 = time.perf_counter()
        await call_next()
        latency = int((time.perf_counter() - t0) * 1000)
        usage = getattr(context.result, "usage_details", None) or {}
        tin, tout = usage.get("input_token_count"), usage.get("output_token_count")
        estimated = tin is None or tout is None
        if estimated:
            tin = _prompt_chars(context) // 4
            tout = len(getattr(context.result, "text", "") or "") // 4
        assert tin is not None and tout is not None
        meter.calls.append(
            Call(
                agent=agent,
                role=role,
                tokens_in=tin,
                tokens_out=tout,
                reasoning_tokens=usage.get("reasoning_output_token_count") or 0,
                latency_ms=latency,
                cost_eur=meter.settings.prices.cost(role, tin, tout),
                estimated=estimated,
            )
        )

    return middleware


def make_client(settings: Settings, role: Role) -> Any:
    """A chat client for the configured provider (function invocation enabled)."""
    if settings.provider == "fake":
        from agents.fake import FakeChatClient

        return FakeChatClient()
    if settings.provider == "openai":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(model=settings.model(role) or None)
    if settings.provider == "foundry":
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import DefaultAzureCredential

        # Azure CLI login locally; the container app's managed identity in Azure.
        return FoundryChatClient(
            project_endpoint=settings.project_endpoint,
            model=settings.model(role),
            credential=DefaultAzureCredential(),
        )
    raise ValueError(f"unknown MODEL_PROVIDER {settings.provider!r}")


def role_options(settings: Settings, role: Role) -> dict[str, Any]:
    """Per-call options: reasoning effort for the reasoning model on Foundry."""
    if role == "reasoning" and settings.provider == "foundry":
        return {"reasoning": {"effort": settings.reasoning_effort}}
    return {}
