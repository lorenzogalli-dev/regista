"""A deterministic, offline chat client (MODEL_PROVIDER=fake).

It answers each structured-output request from the JSON payload in the last user message, the
way a cautious model would, so the whole pipeline runs in tests and CI without a model. It also
records prompt sizes, which is what the cost estimate before a Foundry run is built from.

`FAKE_HALLUCINATE=1` makes the Analyst cite a wrong value, to exercise the Verifier.
"""

import json
import os
import re
from collections.abc import Sequence
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, Content, Message
from agent_framework._middleware import ChatMiddlewareLayer
from agent_framework._tools import FunctionInvocationLayer

from agents import schemas as S

PAYLOAD = re.compile(r"```json\n(.*?)\n```", re.S)
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def payload(messages: Sequence[Message]) -> dict[str, Any]:
    for m in reversed(messages):
        if m.role == "user" and m.text:
            found = PAYLOAD.findall(m.text)
            if found:
                data: dict[str, Any] = json.loads(found[-1])
                return data
    return {}


def _detector(p: dict[str, Any]) -> S.DetectorVerdict:
    c = p["candidate"]
    over = sum(s["above_noise_p95"] for s in c["signals"])
    hint = c["kind"].split("/")[0]
    return S.DetectorVerdict(
        keep=over >= 1,
        mechanism_hint=hint,
        salience=max(1, min(5, round(c["score"]))),
        reason=f"{over} of {len(c['signals'])} signals above their noise level",
    )


def _fmt(metric: str, v: float) -> str:
    if metric in ("possession_time_based", "field_tilt", "pass_completion"):
        return f"{round(v * 100)}%"
    return f"{v:g}"


def _analyst(p: dict[str, Any]) -> S.Explanation:
    c = p["candidate"]
    wanted = {s["metric"] for s in c["signals"]}
    alias = {
        "possession": "possession_time_based",
        "avg_pass_length": "avg_pass_length_m",
        "width": "width_m",
    }
    wanted = {alias.get(m, m) for m in wanted}
    items = [S.Evidence(**e) for e in p["evidence_pack"] if e["metric"] in wanted]
    items = (items or [S.Evidence(**e) for e in p["evidence_pack"]])[:3]
    if os.environ.get("FAKE_HALLUCINATE") == "1":
        items[0] = items[0].model_copy(update={"after": items[0].after + 1.0})
    e = items[0]
    word = "rose" if e.after > e.before else "fell"
    claim = (
        f"{p['team_name']}'s {e.metric.replace('_', ' ')} {word} from {_fmt(e.metric, e.before)} "
        f"to {_fmt(e.metric, e.after)} over the last {p['window_minutes']} minutes."
    )
    return S.Explanation(
        claim=claim,
        mechanism_tag=c["kind"].split("/")[0],
        team_id=c["team_id"],
        player_ids=[c["player_id"]] if c.get("player_id") else [],
        evidence=items,
        confidence=0.6,
    )


def _verifier(p: dict[str, Any]) -> S.TextCheck:
    allowed: set[str] = set()
    ctx = p.get("context_numbers", {})
    allowed |= {str(ctx.get("window_minutes"))} | set(NUMBER.findall(json.dumps(ctx)))
    for e in p["evidence"]:
        for v in (e["before"], e["after"]):
            allowed |= {f"{v:g}", str(round(v * 100)), str(round(v)), f"{v:.1f}", f"{v:.2f}"}
    stray = [n for n in NUMBER.findall(p["claim"]) if n not in allowed]
    return S.TextCheck(
        consistent=not stray, problems=[f"number {n} not in evidence" for n in stray]
    )


def _persona(p: dict[str, Any]) -> S.PersonaSet:
    return S.PersonaSet(
        lines=[
            S.PersonaLine(persona_id=f"{mode}_{lang}", headline=p["headline"][:60], text=p["claim"])
            for mode in S.PERSONA_MODES
            for lang in S.LANGS
        ]
    )


def respond(fmt: type, p: dict[str, Any]) -> Any:
    name = fmt.__name__
    if name == "DetectorVerdict":
        return _detector(p)
    if name == "Explanation":
        return _analyst(p)
    if name == "TextCheck":
        return _verifier(p)
    if name == "Caption":
        return S.Caption(text=p["claim"][:140])
    if name == "PersonaSet":
        return _persona(p)
    if name == "DirectorCue":
        return S.DirectorCue(show=True, delay_ms=0, duration_ms=8000, priority=2)
    raise ValueError(f"fake client has no responder for {name}")


class FakeChatClient(FunctionInvocationLayer[Any], ChatMiddlewareLayer[Any], BaseChatClient[Any]):
    """When the Analyst has tools, it first calls `get_window_stats` once (like a model checking
    the opponent), so the MCP round trip is exercised; then it answers."""

    OTEL_PROVIDER_NAME = "fake"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @staticmethod
    def _tool_call(messages: Sequence[Message], options: Any, fmt: Any) -> Content | None:
        names = {getattr(t, "name", "") for t in options.get("tools") or []}
        if getattr(fmt, "__name__", "") != "Explanation" or "get_window_stats" not in names:
            return None
        if any(c.type == "function_result" for m in messages for c in m.contents):
            return None
        p = payload(messages)
        c = p["candidate"]
        other = next(t for t in p["context"]["teams"] if t != c["team_id"])
        start, end = p["windows"]["after"]
        args = {
            "match_id": p["context"]["match_id"],
            "team_id": other,
            "start_ms": start,
            "end_ms": end,
        }
        return Content.from_function_call(call_id="fake_1", name="get_window_stats", arguments=args)

    async def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options: Any, **kwargs: Any
    ) -> ChatResponse:
        if stream:
            raise NotImplementedError("the fake client does not stream")
        fmt = options.get("response_format")
        call = self._tool_call(messages, options, fmt)
        if call is not None:
            return ChatResponse(messages=[Message(role="assistant", contents=[call])], model="fake")
        text = "ok" if fmt is None else respond(fmt, payload(messages)).model_dump_json()
        return ChatResponse(
            messages=[Message(role="assistant", contents=[Content.from_text(text)])],
            model="fake",
            response_format=fmt,
        )
