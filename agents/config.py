"""Runtime settings from the environment. Switching provider is an env change only:

    MODEL_PROVIDER=fake      scripted, deterministic responses (tests, CI, cost estimates)
    MODEL_PROVIDER=openai    any OpenAI-compatible endpoint (OPENAI_BASE_URL, OPENAI_API_KEY)
    MODEL_PROVIDER=foundry   Microsoft Foundry project (FOUNDRY_PROJECT_ENDPOINT, Azure CLI login)

Models: FOUNDRY_MODEL_FAST (Detector, Verifier, Narrator, Persona, Director) and
FOUNDRY_MODEL_REASONING (Analyst, with FOUNDRY_REASONING_EFFORT).
"""

import os
from dataclasses import dataclass, field
from typing import Literal, cast

Provider = Literal["fake", "openai", "foundry"]
Role = Literal["fast", "reasoning"]


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    return float(raw) if raw.strip() else default


@dataclass(frozen=True)
class Prices:
    """EUR per 1M tokens, from env so they can follow the official price page."""

    fast_in: float = field(default_factory=lambda: _float("PRICE_FAST_IN_EUR_PER_M", 0.10))
    fast_out: float = field(default_factory=lambda: _float("PRICE_FAST_OUT_EUR_PER_M", 0.50))
    reasoning_in: float = field(default_factory=lambda: _float("PRICE_REASONING_IN_EUR_PER_M", 2.0))
    reasoning_out: float = field(
        default_factory=lambda: _float("PRICE_REASONING_OUT_EUR_PER_M", 10.0)
    )

    def cost(self, role: Role, tokens_in: int, tokens_out: int) -> float:
        if role == "fast":
            return (tokens_in * self.fast_in + tokens_out * self.fast_out) / 1e6
        return (tokens_in * self.reasoning_in + tokens_out * self.reasoning_out) / 1e6


@dataclass(frozen=True)
class Settings:
    provider: Provider = field(
        default_factory=lambda: cast(Provider, os.environ.get("MODEL_PROVIDER", "fake"))
    )
    model_fast: str = field(default_factory=lambda: os.environ.get("FOUNDRY_MODEL_FAST", ""))
    model_reasoning: str = field(
        default_factory=lambda: os.environ.get("FOUNDRY_MODEL_REASONING", "")
    )
    reasoning_effort: str = field(
        default_factory=lambda: os.environ.get("FOUNDRY_REASONING_EFFORT", "low")
    )
    project_endpoint: str = field(
        default_factory=lambda: os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
    )
    agent_timeout_s: float = field(default_factory=lambda: _float("AGENT_TIMEOUT_S", 45.0))
    run_budget_eur: float = field(default_factory=lambda: _float("RUN_BUDGET_EUR", 1.0))
    total_cap_eur: float = field(default_factory=lambda: _float("FOUNDRY_TOTAL_CAP_EUR", 8.0))
    analyst_max_tool_calls: int = field(
        default_factory=lambda: int(_float("ANALYST_MAX_TOOL_CALLS", 2))
    )
    prices: Prices = field(default_factory=Prices)

    def model(self, role: Role) -> str:
        return self.model_fast if role == "fast" else self.model_reasoning
