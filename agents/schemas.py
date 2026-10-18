"""Structured outputs of the agents and the records the pipeline stores.

Models return these as structured output (JSON schema); every field an agent fills is checked
downstream: evidence values by code (Verifier), text consistency by the Verifier agent.
"""

from typing import Literal

from pydantic import BaseModel, Field

MechanismTag = Literal[
    "pressing_spell",
    "momentum_shift",
    "tactical_switch",
    "player_arc",
    "none",
]
PERSONA_MODES = ("analyst", "casual", "player_focus")
LANGS = ("en", "it", "es")


class DetectorVerdict(BaseModel):
    """Detector: is this candidate worth explaining?"""

    keep: bool
    mechanism_hint: MechanismTag = Field(description="most likely mechanism, or none")
    salience: int = Field(ge=1, le=5, description="1 = minor, 5 = defining moment")
    reason: str = Field(max_length=200)


class Evidence(BaseModel):
    """One number a claim relies on, as returned by a metrics tool for two windows."""

    tool: Literal["get_window_stats", "get_player_physical"]
    subject: str = Field(description="team_id for get_window_stats, player_id otherwise")
    metric: str
    before_start_ms: int
    before_end_ms: int
    after_start_ms: int
    after_end_ms: int
    before: float
    after: float


class Explanation(BaseModel):
    """Analyst: why the moment matters, with the evidence behind it."""

    claim: str = Field(
        max_length=400, description="one or two sentences, no numbers absent from evidence"
    )
    mechanism_tag: MechanismTag
    team_id: str
    player_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(min_length=1, max_length=4)
    confidence: float = Field(ge=0, le=1)


class TextCheck(BaseModel):
    """Verifier agent: is the claim text consistent with the (already recomputed) evidence?"""

    consistent: bool
    problems: list[str] = Field(default_factory=list, max_length=5)


class Caption(BaseModel):
    text: str = Field(max_length=140)


class PersonaLine(BaseModel):
    persona_id: str = Field(description="<mode>_<lang>, e.g. casual_it")
    headline: str = Field(max_length=60)
    text: str = Field(max_length=240)


class PersonaSet(BaseModel):
    lines: list[PersonaLine]


class DirectorCue(BaseModel):
    """Director: when and how long the moment card goes on air."""

    show: bool
    delay_ms: int = Field(ge=0, le=20_000)
    duration_ms: int = Field(ge=4_000, le=15_000)
    priority: int = Field(ge=1, le=3)
