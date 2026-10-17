"""`metrics summary <match_id>`: a readable match summary built from the tools."""

import argparse
import os
import sys
from pathlib import Path

from metrics.store import MatchStore
from metrics.tools import MatchTools
from sim import io
from sim.replay import merged


def load_store(match_dir: Path) -> MatchStore:
    st = MatchStore(io.read_meta(match_dir))
    for m in merged(match_dir, speed=1.0):
        if m["type"] == "frame":
            st.ingest_frame(m["data"])
        else:
            st.ingest_event(m["data"])
    return st


def _fmt(v: float | None, pct: bool = False, nd: int = 2) -> str:
    if v is None:
        return "-"
    return f"{100 * v:.0f}%" if pct else f"{v:.{nd}f}"


def cmd_summary(a: argparse.Namespace) -> int:
    d = Path(a.data_dir) / a.match_id
    if not (d / io.MATCH_FILE).is_file():
        print(f"error: no match at {d}", file=sys.stderr)
        return 1
    st = load_store(d)
    tools = MatchTools(st)
    m = st.meta
    names = {p.player_id: p.name for p in m.players}
    short = {m.home.team_id: m.home.short, m.away.team_id: m.away.short}
    ctx = tools.get_moment_context(st.now_ms)
    print(
        f"{m.home.name} {ctx.score[m.home.team_id]}-{ctx.score[m.away.team_id]} {m.away.name}"
        f"  ({m.venue}, synthetic data)"
    )
    halves = [
        ("Match", 0, 10**8),
        ("1st half", 0, m.period_end_ms[0]),
        ("2nd half", m.period_end_ms[0], 10**8),
    ]
    rows = [
        ("possession (time-based)", "possession_time_based", True),
        ("field tilt", "field_tilt", True),
        ("PPDA", "ppda", False),
        ("pass completion", "pass_completion", True),
        ("avg pass length (m)", "avg_pass_length_m", False),
        ("shots", "shots", False),
        ("xG", "xg", False),
        ("xT added", "xt_added", False),
        ("control index (0-100)", "control_index", False),
    ]
    for label, start, end in halves:
        stats = {t: tools.get_window_stats(t, start, end) for t in st.team_ids}
        print(f"\n{label:<24}" + "".join(f"{short[t]:>8}" for t in st.team_ids))
        for name, field, pct in rows:
            vals = [getattr(stats[t], field) for t in st.team_ids]
            print(
                f"  {name:<22}"
                + "".join(f"{_fmt(v, pct, 1 if field == 'control_index' else 2):>8}" for v in vals)
            )
    phys = [tools.get_player_physical(p.player_id, 0, 10**8) for p in m.players]
    phys = [p for p in phys if p.minutes_on_pitch > 0]
    print("\nPhysical (top 5 by distance)")
    for p in sorted(phys, key=lambda x: -x.distance_m)[:5]:
        print(
            f"  {names[p.player_id]:<20} {p.distance_m / 1000:5.2f} km"
            f"  HI {p.high_intensity_m:5.0f} m  sprints {p.sprints:3d}"
            f"  top {p.top_speed_kmh:4.1f} km/h"
        )
    best = max(phys, key=lambda x: x.top_speed_ms)
    print(f"  fastest: {names[best.player_id]} {best.top_speed_kmh} km/h")
    kinds: dict[str, int] = {}
    for t in st.triggers:
        kinds[t.kind] = kinds.get(t.kind, 0) + 1
    print(f"\nThreshold triggers: {kinds}")
    passes = [
        (e, st.enriched[e["event_id"]])
        for e in st.events
        if e["type"] == "pass" and e["outcome"] == "complete"
    ]
    print("Top 3 passes by xT added")
    for e, en in sorted(passes, key=lambda x: -(x[1].xt_added or 0))[:3]:
        clock, _ = tools.clock(e["t_ms"])
        print(
            f"  {clock} {names[e['player_id']]:<20} +{en.xt_added:.3f} xT,"
            f" {en.pass_length_m:.0f} m, difficulty {en.pass_difficulty:.2f}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="metrics")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary", help="print a match summary from the metrics tools")
    s.add_argument("match_id")
    s.add_argument("--data-dir", default=os.environ.get("MATCH_DATA_DIR", "data/generated"))
    s.set_defaults(fn=cmd_summary)
    a = p.parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
