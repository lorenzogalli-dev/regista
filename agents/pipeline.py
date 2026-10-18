"""The multi-agent workflow for one candidate moment (Agent Framework graph workflow).

    Detect ─► Analyse ─► Verify ─┬─(approved)─► Narrate ─┐
                ▲                ├─(approved)─► Persona ─┼─► Publish
                └──(retry once)──┤ (approved)─► Direct ──┘
                                 └─(rejected twice / dropped) ─► output

Each agent call has a timeout. Narrator, Persona and Director fall back to deterministic
templates on failure, so a verified moment always produces overlays. In `eval` mode the graph
stops after the Verifier (only detection, explanation and verification are measured).
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler

from agents import evidence as E
from agents import schemas as S
from agents import textcheck
from agents.candidates import Candidate
from agents.config import Role, Settings
from agents.providers import BudgetExceeded, Meter, make_client, metered, role_options
from metrics.tools import MatchTools

PROMPTS = Path(__file__).with_name("prompts")
MAX_ATTEMPTS = 2

Status = Literal["new", "analysing", "retry", "approved", "dropped", "published"]


@dataclass
class Stage:
    stage: str
    ms: int
    outcome: str
    detail: str = ""


@dataclass
class MomentWork:
    candidate: Candidate
    status: Status = "new"
    verdict: S.DetectorVerdict | None = None
    explanation: S.Explanation | None = None
    attempts: int = 0
    rejection: str | None = None
    caption: S.Caption | None = None
    personas: S.PersonaSet | None = None
    cue: S.DirectorCue | None = None
    fallbacks: list[str] = field(default_factory=list)
    stages: list[Stage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "moment_id": self.candidate.candidate_id.replace("c_", "mo_"),
            "candidate": self.candidate.to_dict(),
            "status": self.status,
            "detector": self.verdict.model_dump() if self.verdict else None,
            "explanation": self.explanation.model_dump() if self.explanation else None,
            "attempts": self.attempts,
            "rejection": self.rejection,
            "caption": self.caption.model_dump() if self.caption else None,
            "personas": self.personas.model_dump()["lines"] if self.personas else None,
            "cue": self.cue.model_dump() if self.cue else None,
            "fallbacks": self.fallbacks,
            "stages": [vars(s) for s in self.stages],
        }


def payload_block(data: dict[str, Any]) -> str:
    return "```json\n" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n```"


@dataclass
class Desk:
    """Agents, tools and settings shared by all moments of one run."""

    settings: Settings
    meter: Meter
    tools: MatchTools
    analyst_tools: list[Any] = field(default_factory=list)
    agents: dict[str, Agent] = field(default_factory=dict)

    def __post_init__(self) -> None:
        roles: dict[str, Role] = {
            "detector": "fast",
            "analyst": "reasoning",
            "verifier": "fast",
            "narrator": "fast",
            "persona": "fast",
            "director": "fast",
        }
        for name, role in roles.items():
            text = (PROMPTS / f"{name}.md").read_text()
            if name == "analyst":
                text = text.replace("{max_tool_calls}", str(self.settings.analyst_max_tool_calls))
            self.agents[name] = Agent(
                client=make_client(self.settings, role),
                name=name,
                instructions=text,
                tools=self.analyst_tools if name == "analyst" else None,
                middleware=[metered(self.meter, name, role)],
            )
        self.roles = roles

    async def ask(self, name: str, prompt: str, fmt: type) -> Any:
        opts = {"response_format": fmt, **role_options(self.settings, self.roles[name])}
        res = await asyncio.wait_for(
            self.agents[name].run(prompt, options=cast(Any, opts)), self.settings.agent_timeout_s
        )
        return res.value

    def team_name(self, team_id: str) -> str:
        m = self.tools.store.meta
        return m.home.name if m.home.team_id == team_id else m.away.name

    def player_ids(self, refs: list[str]) -> list[str]:
        """Map player references to ids (models sometimes return names); drop unknown ones."""
        players = self.tools.store.meta.players
        out = []
        for r in refs:
            hit = next(
                (p.player_id for p in players if r == p.player_id or r.startswith(p.name)), None
            )
            if hit and hit not in out:
                out.append(hit)
        return out

    def players_named(self, c: Candidate) -> dict[str, str]:
        """Names of the players a moment involves (candidate player, key-event players)."""
        ids = {c.player_id} | {e["player_id"] for e in c.events} - {None}
        return {
            p.player_id: f"{p.name} (#{p.shirt}, {p.position}, {self.team_name(p.team_id)})"
            for p in self.tools.store.meta.players
            if p.player_id in ids
        }

    def context(self, c: Candidate) -> dict[str, Any]:
        ctx = self.tools.get_moment_context(c.t_ms)
        return {
            "match_id": self.tools.store.meta.match_id,
            "clock": ctx.clock,
            "score": {self.team_name(k): v for k, v in ctx.score.items()},
            "teams": {t: self.team_name(t) for t in self.tools.store.team_ids},
        }


async def _timed(work: MomentWork, stage: str, coro: Any) -> tuple[Any, str]:
    t0 = time.perf_counter()
    try:
        out = await coro
        outcome = "ok"
    except BudgetExceeded:
        raise
    except TimeoutError:
        out, outcome = None, "timeout"
    except Exception as e:  # model or tool failure: logged, never fatal for the run
        out, outcome = None, f"error: {type(e).__name__}: {e}"[:300]
    work.stages.append(Stage(stage, int((time.perf_counter() - t0) * 1000), outcome))
    return out, outcome


# --------------------------------------------------------------------------- templates


def template_caption(desk: Desk, w: MomentWork) -> S.Caption:
    assert w.explanation is not None
    return S.Caption(text=w.explanation.claim[:140])


def template_personas(w: MomentWork) -> S.PersonaSet:
    assert w.explanation is not None
    head = w.explanation.mechanism_tag.replace("_", " ").title()
    return S.PersonaSet(
        lines=[
            S.PersonaLine(persona_id=f"{m}_{lang}", headline=head, text=w.explanation.claim[:240])
            for m in S.PERSONA_MODES
            for lang in S.LANGS
        ]
    )


DEFAULT_CUE = S.DirectorCue(show=True, delay_ms=0, duration_ms=8000, priority=2)


# --------------------------------------------------------------------------- executors


class Detect(Executor):
    def __init__(self, desk: Desk) -> None:
        super().__init__(id="detector")
        self.desk = desk

    @handler
    async def run(self, w: MomentWork, ctx: WorkflowContext[MomentWork, MomentWork]) -> None:
        prompt = "Candidate moment:\n" + payload_block(
            {
                "context": self.desk.context(w.candidate),
                "players": self.desk.players_named(w.candidate),
                "candidate": w.candidate.to_dict(),
            }
        )
        v, outcome = await _timed(
            w, "detector", self.desk.ask("detector", prompt, S.DetectorVerdict)
        )
        w.verdict = v
        if v is None or not v.keep:
            w.status = "dropped"
            w.rejection = "detector: " + (v.reason if v else outcome)
            await ctx.yield_output(w)
            return
        w.status = "analysing"
        await ctx.send_message(w)


class Analyse(Executor):
    def __init__(self, desk: Desk) -> None:
        super().__init__(id="analyst")
        self.desk = desk

    @handler
    async def run(self, w: MomentWork, ctx: WorkflowContext[MomentWork, MomentWork]) -> None:
        c = w.candidate
        before, after = E.windows(c)
        data = {
            "context": self.desk.context(c),
            "players": self.desk.players_named(c),
            "candidate": c.to_dict(),
            "detector": w.verdict.model_dump() if w.verdict else None,
            "team_name": self.desk.team_name(c.team_id),
            "window_minutes": round((after[1] - after[0]) / 60_000),
            "windows": {"before": before, "after": after},
            "evidence_pack": [e.model_dump() for e in E.pack(self.desk.tools, c)],
        }
        if w.rejection:
            data["previous_attempt_rejected_because"] = w.rejection
        prompt = "Explain this moment:\n" + payload_block(data)
        w.attempts += 1
        x, outcome = await _timed(
            w, f"analyst#{w.attempts}", self.desk.ask("analyst", prompt, S.Explanation)
        )
        if x is None:
            w.status = "dropped"
            w.rejection = f"analyst: {outcome}"
            await ctx.yield_output(w)
            return
        x.player_ids = self.desk.player_ids(x.player_ids)
        w.explanation = x
        if x.mechanism_tag == "none":
            w.status = "dropped"
            w.rejection = "analyst: no mechanism fits"
            await ctx.yield_output(w)
            return
        await ctx.send_message(w)


class Verify(Executor):
    """Hybrid: code recomputes every evidence item, then the agent checks the text."""

    def __init__(self, desk: Desk, publish: bool) -> None:
        super().__init__(id="verifier")
        self.desk = desk
        self.publish = publish

    @handler
    async def run(self, w: MomentWork, ctx: WorkflowContext[MomentWork, MomentWork]) -> None:
        assert w.explanation is not None
        t0 = time.perf_counter()
        problems = [p for e in w.explanation.evidence if (p := E.recompute(self.desk.tools, e))]
        w.stages.append(
            Stage(
                "verifier:code",
                int((time.perf_counter() - t0) * 1000),
                "ok" if not problems else "rejected",
                "; ".join(problems)[:300],
            )
        )
        if not problems:
            c = w.candidate
            data = {
                "claim": w.explanation.claim,
                "team": self.desk.team_name(w.explanation.team_id),
                "players": {
                    p.player_id: p.name
                    for p in self.desk.tools.store.meta.players
                    if p.player_id in w.explanation.player_ids
                    or any(e.subject == p.player_id for e in w.explanation.evidence)
                },
                "evidence": [e.model_dump() for e in w.explanation.evidence],
                "context_numbers": {
                    "window_minutes": round((c.window_end_ms - c.window_start_ms) / 60_000),
                    **self.desk.context(c),
                },
            }
            prompt = "Check this claim against its recomputed evidence:\n" + payload_block(data)
            check, outcome = await _timed(
                w, "verifier:text", self.desk.ask("verifier", prompt, S.TextCheck)
            )
            if check is None:
                problems = [f"text check {outcome}"]
            elif not check.consistent:
                problems = check.problems or ["claim inconsistent with evidence"]
                w.stages[-1].outcome = "rejected"
                w.stages[-1].detail = "; ".join(problems)[:300]
        if not problems:
            w.status = "approved"
            w.rejection = None
            if self.publish:
                await ctx.send_message(w)
            else:
                await ctx.yield_output(w)
            return
        w.rejection = "; ".join(problems)[:400]
        if w.attempts < MAX_ATTEMPTS:
            w.status = "retry"
            await ctx.send_message(w)
        else:
            w.status = "dropped"
            await ctx.yield_output(w)


@dataclass
class Part:
    kind: str
    value: Any


class Narrate(Executor):
    def __init__(self, desk: Desk) -> None:
        super().__init__(id="narrator")
        self.desk = desk

    @handler
    async def run(self, w: MomentWork, ctx: WorkflowContext[Part]) -> None:
        assert w.explanation is not None
        prompt = "Verified moment:\n" + payload_block(
            {"context": self.desk.context(w.candidate), "claim": w.explanation.claim}
        )
        cap, _ = await _timed(w, "narrator", self.desk.ask("narrator", prompt, S.Caption))
        await ctx.send_message(Part("caption", cap))


class Persona(Executor):
    def __init__(self, desk: Desk) -> None:
        super().__init__(id="persona")
        self.desk = desk

    @handler
    async def run(self, w: MomentWork, ctx: WorkflowContext[Part]) -> None:
        assert w.explanation is not None
        prompt = "Verified insight:\n" + payload_block(
            {
                "claim": w.explanation.claim,
                "headline": w.explanation.mechanism_tag.replace("_", " "),
                "team": self.desk.team_name(w.explanation.team_id),
                "players": [
                    p.name
                    for p in self.desk.tools.store.meta.players
                    if p.player_id in w.explanation.player_ids
                ],
            }
        )
        ps, _ = await _timed(w, "persona", self.desk.ask("persona", prompt, S.PersonaSet))
        await ctx.send_message(Part("personas", ps))


class Direct(Executor):
    def __init__(self, desk: Desk) -> None:
        super().__init__(id="director")
        self.desk = desk

    @handler
    async def run(self, w: MomentWork, ctx: WorkflowContext[Part]) -> None:
        assert w.verdict is not None
        recent = [
            e["type"]
            for e in self.desk.tools.store.events_between(
                w.candidate.t_ms - 15_000, w.candidate.t_ms + 1
            )
        ]
        prompt = "Moment card ready:\n" + payload_block(
            {
                "salience": w.verdict.salience,
                "recent_events": recent[-8:],
                "context": self.desk.context(w.candidate),
            }
        )
        cue, _ = await _timed(w, "director", self.desk.ask("director", prompt, S.DirectorCue))
        await ctx.send_message(Part("cue", cue))


class Publish(Executor):
    """Fan-in: merges the three parts, filling any failed one with its template, then checks
    the derived texts against the verified claim (code) and replaces any that say more."""

    def check_text(self, w: MomentWork) -> None:
        assert w.explanation is not None and w.caption is not None and w.personas is not None
        claim = w.explanation.claim
        players = {p.player_id: p.name for p in self.desk.tools.store.meta.players}
        allowed = {n for pid, n in players.items() if n in claim}
        extra = {str(round((w.candidate.window_end_ms - w.candidate.window_start_ms) / 60_000))}
        if textcheck.problems(w.caption.text, claim, players, allowed, extra):
            w.caption = template_caption(self.desk, w)
            w.fallbacks.append("caption:text-check")
        template = {line.persona_id: line for line in template_personas(w).lines}
        lines = []
        for line in w.personas.lines:
            bad = textcheck.problems(f"{line.headline} {line.text}", claim, players, allowed, extra)
            if bad:
                w.fallbacks.append(f"{line.persona_id}:text-check: {bad[0]}")
                line = template.get(line.persona_id, line)
            lines.append(line)
        w.personas = S.PersonaSet(lines=lines)

    def __init__(self, desk: Desk, works: dict[str, MomentWork]) -> None:
        super().__init__(id="publisher")
        self.desk = desk
        self.works = works

    @handler
    async def run(self, parts: list[Part], ctx: WorkflowContext[None, MomentWork]) -> None:
        (w,) = self.works.values()
        got = {p.kind: p.value for p in parts}
        w.caption = got.get("caption") or template_caption(self.desk, w)
        w.personas = got.get("personas") or template_personas(w)
        w.cue = got.get("cue") or DEFAULT_CUE
        w.fallbacks = [k for k in ("caption", "personas", "cue") if got.get(k) is None]
        self.check_text(w)
        w.status = "published"
        await ctx.yield_output(w)


async def run_moment(desk: Desk, c: Candidate, mode: Literal["full", "eval"]) -> MomentWork:
    """Build and run the workflow for one candidate."""
    w = MomentWork(candidate=c)
    detect, analyse = Detect(desk), Analyse(desk)
    verify = Verify(desk, publish=mode == "full")
    b = (
        WorkflowBuilder(name="moment", start_executor=detect)
        .add_edge(detect, analyse)
        .add_edge(analyse, verify)
        .add_edge(verify, analyse, condition=lambda m: m.status == "retry")
    )
    if mode == "full":
        narrate, persona, direct = Narrate(desk), Persona(desk), Direct(desk)
        publish = Publish(desk, {c.candidate_id: w})
        for target in (narrate, persona, direct):
            b = b.add_edge(verify, target, condition=lambda m: m.status == "approved")
        b = b.add_fan_in_edges([narrate, persona, direct], publish)
    result = await b.build().run(w)
    outs = result.get_outputs()
    return outs[-1] if outs else w
