"""Export a short clip of a generated match for front-end design work (D5a).

`python -m metrics.export_sample m_1000 --pass-event e_003045 --out web/public/samples/hero.json`

The clip holds public data only (match meta, tracking frames, events) plus numbers computed by
the metrics tools: the pass card of the chosen pass and a before/after window comparison for the
moment card. No ground truth is read; the moment is chosen by hand from tool output.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any

from metrics.cli import load_store
from metrics.tools import MIN_MS, MatchTools
from sim import io

LEAD_MS = 6_000
TAIL_MS = 9_000
WINDOW_MIN = 12


def export(match_dir: Path, pass_event: str) -> dict[str, Any]:
    tools = MatchTools(load_store(match_dir))
    st = tools.store
    ev = next(e for e in st.events if e["event_id"] == pass_event)
    if ev["type"] != "pass":
        raise ValueError(f"{pass_event} is not a pass")
    t = ev["t_ms"]
    start, end = t - LEAD_MS, t + TAIL_MS
    seq = tools.get_sequence(ev["possession_id"])
    card = next(x for x in seq.events if x.event_id == pass_event)
    w = WINDOW_MIN * MIN_MS
    cmp = tools.compare_windows(ev["team_id"], t - 2 * w, t - w, t - w, t)
    ctx = tools.get_moment_context(t)
    frames = [f for f in io.iter_tracking(match_dir) if start <= f["t_ms"] <= end]
    events = [
        e
        for e in st.events
        if start <= e["t_ms"] <= end and e["type"] not in ("pressure", "possession_change")
    ]
    return {
        "note": "Design sample: simulator output and tool numbers; moment text is hand-written.",
        "match": tools.get_match_info().model_dump(),
        "colors": {
            st.meta.home.team_id: st.meta.home.colors,
            st.meta.away.team_id: st.meta.away.colors,
        },
        "period_end_ms": list(st.meta.period_end_ms),
        "clip": {"start_ms": start, "end_ms": end, "pass_ms": t},
        "score": ctx.score,
        "pass_card": {
            **card.model_dump(),
            "team_id": ev["team_id"],
            "recipient_id": ev["recipient_id"],
        },
        "window": {
            "team_id": ev["team_id"],
            "minutes": WINDOW_MIN,
            "deltas": {d.metric: d.model_dump() for d in cmp.deltas},
        },
        "frames": frames,
        "events": events,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m metrics.export_sample")
    ap.add_argument("match_id")
    ap.add_argument("--pass-event", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    data_dir = Path(os.environ.get("MATCH_DATA_DIR", "data/generated"))
    out = export(data_dir / a.match_id, a.pass_event)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"{a.out}: {len(out['frames'])} frames, {len(out['events'])} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
