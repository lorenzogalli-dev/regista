"""Data contracts for simulator output (SPEC §3). Shared with the API and the metrics engine."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
TICK_MS = 100

EventType = Literal[
    "kickoff",
    "pass",
    "carry",
    "shot",
    "save",
    "goal",
    "tackle",
    "interception",
    "clearance",
    "pressure",
    "foul",
    "card",
    "sub",
    "ball_recovery",
    "possession_change",
    "period_start",
    "period_end",
]

StorylineType = Literal[
    "pressing_spell", "fatigue_drop", "momentum_shift", "tactical_switch", "player_arc"
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TeamStyle(_Model):
    press_intensity: float = Field(ge=0, le=1)
    directness: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)


class Team(_Model):
    team_id: str
    name: str
    short: str
    colors: list[str]
    formation: str
    style: TeamStyle


class PlayerAttrs(_Model):
    top_speed_ms: float
    accel: float = Field(ge=0, le=1)
    passing: float = Field(ge=0, le=1)
    finishing: float = Field(ge=0, le=1)
    defending: float = Field(ge=0, le=1)
    stamina: float = Field(ge=0, le=1)


class Player(_Model):
    player_id: str
    team_id: str
    name: str
    shirt: int
    position: str
    starter: bool
    attrs: PlayerAttrs


class MatchMeta(_Model):
    match_id: str
    seed: int
    competition: str
    venue: str
    home: Team
    away: Team
    players: list[Player]
    period_end_ms: list[int] = Field(description="t_ms at which each period ends")


class Event(_Model):
    event_id: str
    match_id: str
    t_ms: int
    period: int
    type: EventType
    team_id: str | None
    player_id: str | None
    x: float
    y: float
    end_x: float | None = None
    end_y: float | None = None
    outcome: str | None = None
    recipient_id: str | None = None
    possession_id: int
    qualifiers: dict[str, Any] = Field(default_factory=dict)


class ExpectedSignal(_Model):
    metric: str
    team: str | None = None
    player: str | None = None
    direction: Literal["up", "down"]


class Storyline(_Model):
    storyline_id: str
    type: StorylineType
    variant: str | None = None
    start_ms: int
    end_ms: int
    team_id: str
    actors: list[str]
    mechanism: dict[str, str]
    expected_signals: list[ExpectedSignal]
    canonical_explanation: str


class GroundTruth(_Model):
    match_id: str
    seed: int
    control: bool
    storylines: list[Storyline]
