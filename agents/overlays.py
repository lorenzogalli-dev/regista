"""Overlay timeline (SPEC §6.2) and pipeline events, shared by live sessions and recorded runs.

Tier 0 (code only, immediate): speed badge, shot speed, pass card (difficult passes), stat
compare every STAT_EVERY_MS, and the control-index ribbon (one point per team per minute).
Tier 1 (agents): for each kept candidate the Director puts a deterministic template card on air
first (state `pending`, amber; its numbers come from code), then replaces it with the verified
model text (state `verified`, with the persona texts and the seal) when the pipeline finishes,
or withdraws it if the moment is dropped. Live sessions emit these as they happen; a recorded
run stores them with the real latencies measured when it was produced.
"""

from dataclasses import dataclass, field
from typing import Any

from agents.candidates import Candidate
from metrics import models
from metrics.store import MatchStore
from metrics.tools import MatchTools

MIN_MS = 60_000
STAT_EVERY_MS = 15 * MIN_MS
RIBBON_WINDOW_MS = 5 * MIN_MS
TIER0_DURATION_MS = {"speed_badge": 3500, "shot_speed": 5000, "pass_card": 6000}
# On air, speed badges are for peaks only, and not too often.
SPEED_BADGE_MIN_KMH = 33.0
SPEED_BADGE_GAP_MS = 3 * MIN_MS
SHARE_METRICS = {"possession", "field_tilt", "pass_completion"}
LABEL = {
    "possession": "time-based possession",
    "field_tilt": "field tilt",
    "ppda": "PPDA",
    "pass_completion": "pass completion",
    "avg_pass_length": "average pass length",
    "width": "width",
    "progressive_passes": "progressive passes per minute",
    "touches": "touches per minute",
}
HEADLINE = {
    "pressing_spell": "Pressing harder",
    "momentum_shift": "Taking control",
    "tactical_switch/long_ball": "Going direct",
    "tactical_switch/wide": "Stretching the pitch",
    "player_arc": "Driving the play",
}


def overlay(
    oid: str,
    kind: str,
    show_at: int,
    duration: int,
    payload: dict[str, Any],
    *,
    priority: int = 3,
    anchor: dict[str, Any] | None = None,
    source: str | None = None,
    tier: int = 0,
) -> dict[str, Any]:
    return {
        "overlay_id": oid,
        "source_moment_id": source,
        "tier": tier,
        "show_at_ms": int(show_at),
        "duration_ms": int(duration),
        "priority": priority,
        "kind": kind,
        "anchor": anchor or {"type": "screen"},
        "payload": payload,
    }


@dataclass
class Tier0Feed:
    """Turns the live store into tier-0 overlays; call `poll()` after ingesting."""

    store: MatchStore
    seen_triggers: int = 0
    next_stat: int = STAT_EVERY_MS
    next_ribbon: int = MIN_MS
    last_speed_badge: int = -SPEED_BADGE_GAP_MS
    count: int = 0
    tools: MatchTools = field(init=False)

    def __post_init__(self) -> None:
        self.tools = MatchTools(self.store)

    def _id(self) -> str:
        self.count += 1
        return f"o0_{self.count:04d}"

    def poll(self) -> list[dict[str, Any]]:
        st = self.store
        out: list[dict[str, Any]] = []
        for tr in st.triggers[self.seen_triggers :]:
            if tr.kind == "speed":
                if tr.value * 3.6 < SPEED_BADGE_MIN_KMH:
                    continue
                if tr.t_ms - self.last_speed_badge < SPEED_BADGE_GAP_MS:
                    continue
                self.last_speed_badge = tr.t_ms
            out.append(self._trigger(tr))
        self.seen_triggers = len(st.triggers)
        while self.next_ribbon <= st.now_ms:
            t = self.next_ribbon
            out.append(self._ribbon(t))
            self.next_ribbon += MIN_MS
        while self.next_stat <= st.now_ms:
            out.append(self._stat(self.next_stat))
            self.next_stat += STAT_EVERY_MS
        return out

    def _trigger(self, tr: Any) -> dict[str, Any]:
        anchor = {"type": "player", "player_id": tr.player_id}
        if tr.kind == "speed":
            return overlay(
                self._id(),
                "speed_badge",
                tr.t_ms,
                TIER0_DURATION_MS["speed_badge"],
                {
                    "value": round(tr.value * 3.6, 1),
                    "unit": "km/h",
                    "player_id": tr.player_id,
                    "team_id": tr.team_id,
                },
                anchor=anchor,
            )
        e = next(x for x in self.store.events if x["event_id"] == tr.event_id)
        en = self.store.enriched.get(e["event_id"])
        if tr.kind == "shot_speed":
            return overlay(
                self._id(),
                "shot_speed",
                tr.t_ms,
                TIER0_DURATION_MS["shot_speed"],
                {
                    "value": round(tr.value * 3.6, 1),
                    "unit": "km/h",
                    "player_id": tr.player_id,
                    "team_id": tr.team_id,
                    "xg": round(en.xg, 2) if en and en.xg else None,
                    "outcome": e["outcome"],
                },
                anchor=anchor,
                priority=2,
            )
        return overlay(
            self._id(),
            "pass_card",
            tr.t_ms,
            TIER0_DURATION_MS["pass_card"],
            {
                "player_id": tr.player_id,
                "recipient_id": e["recipient_id"],
                "team_id": tr.team_id,
                "x": e["x"],
                "y": e["y"],
                "end_x": e["end_x"],
                "end_y": e["end_y"],
                "pass_length_m": round(en.pass_length_m or 0.0, 1) if en else None,
                "pass_progression_m": round(en.pass_progression_m or 0.0, 1) if en else None,
                "pass_difficulty": round(tr.value, 3),
                "ball_speed_ms": e["qualifiers"].get("ball_speed_ms"),
            },
            anchor={"type": "pitch", "x": e["x"], "y": e["y"]},
        )

    def _ribbon(self, t: int) -> dict[str, Any]:
        start = max(0, t - RIBBON_WINDOW_MS)
        values = {}
        for team in self.store.team_ids:
            v = models.control_index(self.store.control_components(team, start, t))
            values[team] = None if v is None else round(v, 1)
        return overlay(self._id(), "momentum_bar", t, MIN_MS, {"control_index": values})

    def _stat(self, t: int) -> dict[str, Any]:
        start = t - STAT_EVERY_MS
        rows = {}
        for team in self.store.team_ids:
            w = self.tools.get_window_stats(team, start, t)
            rows[team] = {
                "possession_time_based": w.possession_time_based,
                "field_tilt": w.field_tilt,
                "ppda": w.ppda,
            }
        return overlay(
            self._id(),
            "stat_compare",
            t + 2000,
            9000,
            {"window_minutes": STAT_EVERY_MS // MIN_MS, "teams": rows},
            priority=3,
        )


def _fmt(metric: str, v: float) -> str:
    if metric in SHARE_METRICS:
        return f"{round(v * 100)}%"
    return f"{v:.1f}"


def template_card(c: Candidate, team_name: str, player_name: str | None) -> dict[str, Any]:
    """Deterministic card from the candidate's code-computed signals (no model text)."""
    sigs = sorted(c.signals, key=lambda s: -s.z)[:2]
    lines = [
        f"{LABEL.get(s.metric, s.metric).capitalize()} {_fmt(s.metric, s.before_value)} → "
        f"{_fmt(s.metric, s.window_value)}"
        for s in sigs
    ]
    minutes = round((c.window_end_ms - c.window_start_ms) / MIN_MS)
    who = player_name or team_name
    return {
        "headline": f"{who}: {HEADLINE.get(c.kind, 'Something is changing').lower()}?",
        "text": f"Last {minutes} minutes vs before: " + "; ".join(lines) + ".",
        "team_id": c.team_id,
        "player_id": c.player_id,
    }


def stage_offsets(stages: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int, int]]:
    """(stage, start offset, end offset) in ms from the candidate time. Narrator, Persona and
    Director run in parallel after the Verifier."""
    out = []
    t = 0
    parallel = ("narrator", "persona", "director")
    par_start: int | None = None
    for s in stages:
        if s["stage"] in parallel:
            par_start = t if par_start is None else par_start
            out.append((s, par_start, par_start + s["ms"]))
        else:
            out.append((s, t, t + s["ms"]))
            t += s["ms"]
    return out


def pipeline_events(m: dict[str, Any]) -> list[dict[str, Any]]:
    """Stage start/end events of one recorded moment, timed on the match clock."""
    c = m["candidate"]
    base = c["t_ms"]
    out = [
        {
            "type": "pipeline",
            "at_ms": base,
            "moment_id": m["moment_id"],
            "stage": "candidate",
            "phase": "end",
            "outcome": "ok",
            "ms": 0,
            "detail": c["kind"],
        },
    ]
    for s, a, b in stage_offsets(m["stages"]):
        out.append(
            {
                "type": "pipeline",
                "at_ms": base + a,
                "moment_id": m["moment_id"],
                "stage": s["stage"],
                "phase": "start",
            }
        )
        out.append(
            {
                "type": "pipeline",
                "at_ms": base + b,
                "moment_id": m["moment_id"],
                "stage": s["stage"],
                "phase": "end",
                "outcome": s["outcome"],
                "ms": s["ms"],
                "detail": s.get("detail", ""),
            }
        )
    end = max((b for _, _, b in stage_offsets(m["stages"])), default=0)
    out.append(
        {
            "type": "pipeline",
            "at_ms": base + end,
            "moment_id": m["moment_id"],
            "stage": "result",
            "phase": "end",
            "outcome": m["status"],
            "detail": m.get("rejection") or "",
        }
    )
    return out


def moment_overlays(m: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
    """Tier-1 overlays of one recorded moment: template when the Detector keeps it, then the
    verified card (or a withdrawal), at the measured latencies."""
    c = m["candidate"]
    mid = m["moment_id"]
    offs = stage_offsets(m["stages"])
    det_end = next((b for s, _, b in offs if s["stage"] == "detector"), 0)
    end = max((b for _, _, b in offs), default=0)
    if not (m["detector"] or {}).get("keep"):
        return []
    out = [
        overlay(
            f"{mid}_t",
            "moment_card",
            c["t_ms"] + det_end,
            15_000,
            {**template, "state": "pending"},
            priority=2,
            source=mid,
            tier=1,
        )
    ]
    if m["status"] == "published":
        x = m["explanation"]
        cue = m["cue"] or {}
        texts = {
            p["persona_id"]: {"headline": p["headline"], "text": p["text"]}
            for p in m["personas"] or []
        }
        out.append(
            overlay(
                f"{mid}_v",
                "moment_card",
                c["t_ms"] + end + cue.get("delay_ms", 0),
                cue.get("duration_ms", 8000),
                {
                    "state": "verified",
                    "replaces": f"{mid}_t",
                    "claim": x["claim"],
                    "mechanism_tag": x["mechanism_tag"],
                    "team_id": x["team_id"],
                    "player_ids": x["player_ids"],
                    "texts": texts,
                    "seal": {"passed": len(x["evidence"]), "total": len(x["evidence"])},
                    "evidence": x["evidence"],
                    "fallbacks": m["fallbacks"],
                },
                priority=cue.get("priority", 2),
                source=mid,
                tier=1,
            )
        )
        if m["caption"]:
            out.append(
                overlay(
                    f"{mid}_c",
                    "caption",
                    c["t_ms"] + end,
                    8000,
                    {"text": m["caption"]["text"]},
                    source=mid,
                    tier=1,
                )
            )
    else:
        out.append(
            overlay(
                f"{mid}_w",
                "moment_card",
                c["t_ms"] + end,
                0,
                {"state": "withdrawn", "replaces": f"{mid}_t", "reason": m.get("rejection") or ""},
                source=mid,
                tier=1,
            )
        )
    return out
