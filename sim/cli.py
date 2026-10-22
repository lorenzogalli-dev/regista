"""Command line: `sim generate`, `sim watch`, `sim digest`, `sim plausibility`."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from sim import io
from sim.generate import match_id, simulate
from sim.seeds import CONTROL_SEEDS, DEV_SEEDS

NOTABLE = {"kickoff", "shot", "goal", "card", "sub", "period_start", "period_end"}


def _clock(t_ms: int, period_ends: list[int]) -> str:
    p1 = period_ends[0]
    s = t_ms // 1000 if t_ms < p1 else 45 * 60 + (t_ms - p1) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def cmd_generate(a: argparse.Namespace) -> int:
    out = Path(a.out) if a.out else Path("data/generated") / match_id(a.seed)
    gt = Path(a.gt_dir or os.environ.get("GROUND_TRUTH_DIR", "data/ground_truth"))
    try:
        io.check_separation(out, gt)
    except io.GroundTruthLeak as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    result, truth = simulate(a.seed, control=a.control)
    t1 = time.perf_counter()
    paths = io.write_match(result, truth, out, gt)
    t2 = time.perf_counter()
    m = result.meta
    print(
        f"{m.match_id}: {m.home.name} {result.score[0]}-{result.score[1]} {m.away.name} ({m.venue})"
    )
    print(
        f"  events={len(result.events)} frames={len(result.t_ms)} "
        f"storylines={len(truth.storylines)}"
    )
    print(f"  simulate {t1 - t0:.1f}s, write {t2 - t1:.1f}s")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    return 0


def cmd_digest(a: argparse.Namespace) -> int:
    print(json.dumps(io.content_digest(Path(a.match_dir)), indent=2, sort_keys=True))
    return 0


def cmd_reindex(a: argparse.Namespace) -> int:
    for d in a.match_dirs:
        io.reindex_tracking(Path(d))
        print(f"{d}: indexed, content unchanged")
    return 0


def cmd_plausibility(a: argparse.Namespace) -> int:
    from sim.plausibility import summarise_seeds

    seeds = list(CONTROL_SEEDS if a.set == "control" else DEV_SEEDS)
    rows = summarise_seeds(seeds, workers=a.workers)
    for r in rows:
        print(json.dumps(r.as_dict()))
    return 0


def cmd_watch(a: argparse.Namespace) -> int:
    from websockets.sync.client import connect

    url = f"ws://{a.host}/ws/replay/{a.match_id}?speed={a.speed}&from_ms={a.from_ms}"
    score = [0, 0]
    n_events = n_frames = 0
    teams: list[str] = []
    ends: list[int] = [0, 0]
    shorts: dict[str, str] = {}
    names: dict[str, str] = {}
    last_status = -1
    t_wall = time.monotonic()
    with connect(url, max_size=None) as ws:
        for raw in ws:
            msg = json.loads(raw)
            kind = msg["type"]
            if kind == "meta":
                m = msg["data"]
                teams = [m["home"]["team_id"], m["away"]["team_id"]]
                shorts = {
                    m["home"]["team_id"]: m["home"]["short"],
                    m["away"]["team_id"]: m["away"]["short"],
                }
                names = {p["player_id"]: p["name"] for p in m["players"]}
                ends = m["period_end_ms"]
                print(
                    f"{m['home']['name']} v {m['away']['name']} at {m['venue']}  "
                    f"(speed {msg['speed']}x)"
                )
            elif kind == "event":
                n_events += 1
                e = msg["data"]
                if e["type"] == "goal":
                    score[teams.index(e["team_id"])] += 1
                if e["type"] in NOTABLE:
                    who = names.get(e["player_id"] or "", "")
                    team = shorts.get(e["team_id"] or "", "")
                    extra = e["outcome"] or ""
                    if e["type"] == "sub":
                        q = e["qualifiers"]
                        extra = f"{names[q['player_out']]} -> {names[q['player_in']]}"
                    print(
                        f"  {_clock(e['t_ms'], ends)}  {e['type']:<12} {team:<4} {who:<18} {extra}"
                        f"   [{score[0]}-{score[1]}]"
                    )
            elif kind == "frame":
                n_frames += 1
                f = msg["data"]
                minute = f["t_ms"] // 300_000
                if minute != last_status:
                    last_status = minute
                    b = f["ball"]
                    print(
                        f"  {_clock(f['t_ms'], ends)}  frame        "
                        f"ball=({b['x']:.1f},{b['y']:.1f}) "
                        f"players={len(f['players'])} frames_rx={n_frames}"
                    )
            elif kind == "error":
                print(f"error: {msg['detail']}", file=sys.stderr)
                return 1
            elif kind == "end":
                break
    wall = time.monotonic() - t_wall
    print(f"end: {score[0]}-{score[1]}  events={n_events} frames={n_frames} wall={wall:.1f}s")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sim")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="simulate one match and write it to disk")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--out", help="output dir (default data/generated/m_<seed>)")
    g.add_argument(
        "--gt-dir", help="ground-truth dir (default $GROUND_TRUTH_DIR or data/ground_truth)"
    )
    g.add_argument(
        "--control",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="force zero storylines (default: seed in the control set)",
    )
    g.set_defaults(fn=cmd_generate)

    d = sub.add_parser("digest", help="sha256 of a generated match's uncompressed content")
    d.add_argument("match_dir")
    d.set_defaults(fn=cmd_digest)

    r = sub.add_parser("reindex", help="rewrite tracking files generated before the seek index")
    r.add_argument("match_dirs", nargs="+")
    r.set_defaults(fn=cmd_reindex)

    pl = sub.add_parser("plausibility", help="summary stats over a seed set")
    pl.add_argument("--set", choices=["dev", "control"], default="dev")
    pl.add_argument("--workers", type=int, default=4)
    pl.set_defaults(fn=cmd_plausibility)

    w = sub.add_parser("watch", help="terminal client for the replay WebSocket")
    w.add_argument("match_id")
    w.add_argument("--speed", type=float, default=4.0)
    w.add_argument("--from-ms", type=int, default=0)
    w.add_argument("--host", default="localhost:8000")
    w.set_defaults(fn=cmd_watch)

    a = p.parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
