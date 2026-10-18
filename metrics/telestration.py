"""Telestration for a verified moment: what to draw on the pitch while the moment replays.

Plain code over public match data (events, first tracking frame of each period), driven by the
explanation's mechanism and the metrics its evidence cites. The shapes show where the cited
numbers come from: the zone where a team wins the ball back, the flank it attacks, its long
passes, a player's progressive passes. Labels carry counts computed here, never model text.

Coordinates are raw pitch coordinates for the period in which the moment goes on air, so the
drawing lines up with the frozen frame.
"""

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from metrics import counters as C
from sim import io
from sim.schema import PITCH_LENGTH, PITCH_WIDTH

REGAINS = {"ball_recovery", "interception", "tackle"}
MAX_ARROWS = 6
MAX_DOTS = 40


@lru_cache(maxsize=16)
def directions(match_dir: Path) -> dict[tuple[str, int], int]:
    """+1 if a team attacks towards x = 105 in a period: it defends the goal its players stand
    closest to at the period's first frame (the same rule as `metrics.data`)."""
    meta = io.read_meta(match_dir)
    team = {p.player_id: p.team_id for p in meta.players}
    out: dict[tuple[str, int], int] = {}
    with gzip.open(match_dir / io.TRACKING_FILE, "rt", encoding="utf-8") as f:
        for line in f:
            period = 1 if not out else 2
            if period == 2 and '"period":2' not in line[:40]:
                continue
            frame = json.loads(line)
            for t in (meta.home.team_id, meta.away.team_id):
                xs = [p["x"] for p in frame["players"] if team.get(p["player_id"]) == t]
                out[(t, period)] = 1 if float(np.mean(xs)) < PITCH_LENGTH / 2 else -1
            if period == 2:
                break
    return out


def _period_at(meta: Any, t_ms: int) -> int:
    return 1 if t_ms < meta.period_end_ms[0] else 2


def telestration(match_dir: Path, moment: dict[str, Any], show_at_ms: int) -> dict[str, Any] | None:
    ex = moment.get("explanation")
    if not ex or not ex.get("evidence"):
        return None
    meta = io.read_meta(match_dir)
    dirs = directions(match_dir)
    team = ex["team_id"]
    period = _period_at(meta, show_at_ms)

    def att(t: str, per: int, x: float, y: float) -> tuple[float, float]:
        return (x, y) if dirs[(t, per)] == 1 else (PITCH_LENGTH - x, PITCH_WIDTH - y)

    def raw(x: float, y: float) -> tuple[float, float]:
        """Attacking frame of `team` → raw coordinates in the on-air period."""
        return (x, y) if dirs[(team, period)] == 1 else (PITCH_LENGTH - x, PITCH_WIDTH - y)

    def box(x0: float, y0: float, x1: float, y1: float) -> dict[str, float]:
        (a, b), (c, d) = raw(x0, y0), raw(x1, y1)
        return {
            "x0": round(min(a, c), 2),
            "y0": round(min(b, d), 2),
            "x1": round(max(a, c), 2),
            "y1": round(max(b, d), 2),
        }

    ev0 = ex["evidence"][0]
    start, end = ev0["after_start_ms"], ev0["after_end_ms"]
    minutes = max(1, round((end - start) / 60_000))
    window = [e for e in io.iter_events(match_dir) if start <= e["t_ms"] < end]
    metrics = {e["metric"] for e in ex["evidence"]}
    players = [p for p in ex.get("player_ids", []) if p]
    out: dict[str, Any] = {
        "moment_id": moment["moment_id"],
        "team_id": team,
        "players": players,
        "zones": [],
        "arrows": [],
        "dots": [],
        "label": "",
        "kind": "",
    }

    def own(e: dict[str, Any]) -> bool:
        return bool(e["team_id"] == team)

    def arrow(e: dict[str, Any]) -> dict[str, float]:
        sx, sy = att(team, e["period"], e["x"], e["y"])
        tx, ty = att(team, e["period"], e["end_x"], e["end_y"])
        (a, b), (c, d) = raw(sx, sy), raw(tx, ty)
        return {"x": round(a, 2), "y": round(b, 2), "end_x": round(c, 2), "end_y": round(d, 2)}

    def dot(e: dict[str, Any]) -> dict[str, float]:
        x, y = raw(*att(team, e["period"], e["x"], e["y"]))
        return {"x": round(x, 2), "y": round(y, 2)}

    mech = ex.get("mechanism_tag")
    if mech == "player_arc" and players:
        p = players[0]
        prog = [
            e
            for e in window
            if e["type"] == "pass"
            and e["player_id"] == p
            and e["outcome"] == "complete"
            and C.is_progressive(
                att(team, e["period"], e["x"], e["y"])[0],
                att(team, e["period"], e["end_x"], e["end_y"])[0],
            )
        ]
        out["kind"] = "progressive"
        out["arrows"] = [arrow(e) for e in prog[-MAX_ARROWS:]]
        out["label"] = f"{len(prog)} progressive passes in {minutes} min"
    elif "width_m" in metrics or any(m.startswith("flank") for m in metrics):
        # Width: share of the team's passes and carries that start in the wide channels.
        moves = [e for e in window if own(e) and e["type"] in ("pass", "carry")]
        wide = [
            e
            for e in moves
            if not C.FLANK_RIGHT_Y < att(team, e["period"], e["x"], e["y"])[1] < C.FLANK_LEFT_Y
        ]
        out["kind"] = "width"
        out["zones"] = [
            box(0.0, C.FLANK_LEFT_Y, PITCH_LENGTH, PITCH_WIDTH),
            box(0.0, 0.0, PITCH_LENGTH, C.FLANK_RIGHT_Y),
        ]
        out["dots"] = [dot(e) for e in wide][-MAX_DOTS:]
        share = round(100 * len(wide) / len(moves)) if moves else 0
        out["label"] = f"{share}% of passes and carries start out wide · last {minutes} min"
    elif "avg_pass_length_m" in metrics:
        passes = [e for e in window if own(e) and e["type"] == "pass"]
        lengths = [float(np.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"])) for e in passes]
        longest = sorted(zip(lengths, range(len(passes)), strict=True), reverse=True)[:MAX_ARROWS]
        out["kind"] = "long"
        out["arrows"] = [arrow(passes[i]) for _, i in sorted(longest, key=lambda x: x[1])]
        avg = sum(lengths) / len(lengths) if lengths else 0.0
        out["label"] = f"{len(passes)} passes · average {avg:.1f} m · last {minutes} min"
    elif mech == "pressing_spell" or "ppda" in metrics:
        regains = [e for e in window if own(e) and e["type"] in REGAINS]
        pts = [att(team, e["period"], e["x"], e["y"]) for e in regains]
        high = [x for x, _ in pts if x >= PITCH_LENGTH / 2]
        out["kind"] = "press"
        if pts:
            xs = np.array([x for x, _ in pts])
            lo, hi = (float(v) for v in np.percentile(xs, [40, 95]))
            out["zones"] = [box(max(0.0, lo), 0.0, min(PITCH_LENGTH, hi), PITCH_WIDTH)]
        out["dots"] = [dot(e) for e in regains][-MAX_DOTS:]
        out["label"] = (
            f"{len(high)} of {len(pts)} ball regains in the opponent half · last {minutes} min"
        )
    else:

        def f3(t: str) -> list[dict[str, Any]]:
            return [
                e
                for e in window
                if e["team_id"] == t
                and e["type"] in C.F3_TYPES
                and att(t, e["period"], e["x"], e["y"])[0] >= C.FINAL_THIRD_X
            ]

        other = meta.away.team_id if team == meta.home.team_id else meta.home.team_id
        ours, theirs = f3(team), f3(other)
        out["kind"] = "territory"
        out["zones"] = [box(C.FINAL_THIRD_X, 0.0, PITCH_LENGTH, PITCH_WIDTH)]
        out["dots"] = [dot(e) for e in ours][-MAX_DOTS:]
        out["label"] = f"Final-third ball actions, last {minutes} min: {len(ours)} vs {len(theirs)}"
    return out


def run_telestration(run: dict[str, Any], match_dir: Path) -> list[dict[str, Any]]:
    """One telestration per verified moment card in a recorded run, keyed to when it airs."""
    shown = {
        o["source_moment_id"]: o["show_at_ms"]
        for o in run.get("overlays", [])
        if o["kind"] == "moment_card" and o["payload"].get("state") == "verified"
    }
    out = []
    for m in run.get("moments", []):
        if m["moment_id"] not in shown:
            continue
        t = telestration(match_dir, m, shown[m["moment_id"]])
        if t:
            out.append({**t, "show_at_ms": shown[m["moment_id"]]})
    return out


def highlights(match_dir: Path) -> list[dict[str, Any]]:
    """Goals, shots and red cards for the timeline (public events only)."""
    out = []
    for e in io.iter_events(match_dir):
        if e["type"] == "goal" or (e["type"] == "card" and e["outcome"] == "red"):
            kind = "goal" if e["type"] == "goal" else "red_card"
        elif e["type"] == "shot" and e["outcome"] != "goal":
            kind = "shot"
        else:
            continue
        out.append(
            {"t_ms": e["t_ms"], "kind": kind, "team_id": e["team_id"], "player_id": e["player_id"]}
        )
    return out
