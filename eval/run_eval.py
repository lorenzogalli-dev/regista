"""Evaluation harness: run the agent pipeline (eval mode) on a seed set and score it.

    uv run --env-file .env python -m eval.run_eval --set dev        # dev seeds 1000-1019
    uv run --env-file .env python -m eval.run_eval --set official   # 5000-5019 + 9000-9009

The official set runs once: the harness refuses to start if its report already exists. Matches
are generated when missing (public files to MATCH_DATA_DIR, ground truth to GROUND_TRUTH_DIR);
the pipeline only ever reads the public files. Outputs: `report.json`, `report.html` and every
run JSON (the recorded agent outputs the numbers come from).
"""

import argparse
import asyncio
import html
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from agents.config import Settings
from agents.run import run_match
from eval.score import score
from sim.generate import simulate
from sim.io import write_match
from sim.seeds import CONTROL_SEEDS, DEV_SEEDS, EVAL_SEEDS

SETS = {
    "dev": (list(DEV_SEEDS), Path("eval/out/dev")),
    "official": (list(EVAL_SEEDS) + list(CONTROL_SEEDS), Path("docs/eval")),
}


def ensure_match(seed: int, data_dir: Path, gt_dir: Path) -> str:
    match_id = f"m_{seed}"
    if not (data_dir / match_id).is_dir():
        write_match(*simulate(seed), data_dir / match_id, gt_dir)
    return match_id


def _row(cells: list[Any], tag: str = "td") -> str:
    return "<tr>" + "".join(f"<{tag}>{html.escape(str(c))}</{tag}>" for c in cells) + "</tr>"


def render_html(r: dict[str, Any], title: str) -> str:
    cats = r["categories"]
    rows = [
        _row(["Storyline recall (window midpoint ± 3 min)", f"{r['recall']:.0%}"]),
        _row(["Storyline recall (emission time ± 3 min)", f"{r['recall_strict']:.0%}"]),
        _row(["Precision (classic)", f"{r['precision']:.0%}"]),
        _row(["Precision@3 (moments the Director airs)", f"{r['precision_at_3']:.0%}"]),
        _row(["Evidence validity (independent recomputation)", f"{r['evidence_validity']:.0%}"]),
        _row(["Verifier rejection rate", f"{r['verifier_rejection_rate']:.0%}"]),
        _row(["Approved explanations", r["approved"]]),
        _row(["… storyline hits", cats["storyline_hit"]]),
        _row(
            [
                "… unplanted, evidence-backed (real patterns, not errors)",
                cats["unplanted_evidence_backed"],
            ]
        ),
        _row(["… unsupported", cats["unsupported"]]),
    ]
    if r["control_matches"]:
        rows.append(
            _row(["Approved per control match (no storylines)", r["control_approved_per_match"]])
        )
    by_type = [
        _row([k + (" (difficult)" if v["difficult"] else ""), f"{v['hit']}/{v['of']}"])
        for k, v in r["recall_by_type"].items()
    ]
    control = [_row([k, v]) for k, v in r["control_approved_by_tag"].items()]
    lat = [_row([k, v["p50"], v["p95"]]) for k, v in r["latency_ms"].items()]
    css = (
        "body{font-family:Inter,system-ui,sans-serif;background:#06110c;color:#f2f5f3;"
        "max-width:860px;margin:40px auto;padding:0 16px}h1{font-size:28px}h2{font-size:18px;"
        "margin-top:32px;color:#9fb0a7;text-transform:uppercase;letter-spacing:.08em}"
        "table{border-collapse:collapse;width:100%}td,th{padding:6px 10px;border-bottom:1px solid"
        " rgba(242,245,243,.14);text-align:left;font-variant-numeric:tabular-nums}"
        "p{color:#9fb0a7;line-height:1.5}"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{css}</style></head><body>
<h1>{html.escape(title)}</h1>
<p>{r["storyline_matches"]} storyline matches ({r["storylines"]} hidden storylines),
{r["control_matches"]} control matches. Provider {html.escape(str(r["provider"]))},
models {html.escape(json.dumps(r["models"]))}. {r["calls"]} model calls,
{r["cost_eur"]:.2f} EUR{" (estimated, fake client)" if r["provider"] == "fake" else ""}.
All data is synthetic.</p>
<h2>Summary</h2><table>{"".join(rows)}</table>
<h2>Recall by storyline type</h2><table>{"".join(by_type)}</table>
<h2>Control matches: approved explanations by tag</h2>
<table>{"".join(control) or _row(["none", 0])}</table>
<h2>Latency (ms)</h2><table>{_row(["stage", "p50", "p95"], "th")}{"".join(lat)}</table>
</body></html>
"""


async def run_set(name: str, seeds: list[int], out: Path, settings: Settings) -> dict[str, Any]:
    data_dir = Path(os.environ.get("MATCH_DATA_DIR", "data/generated"))
    gt_dir = Path(os.environ.get("GROUND_TRUTH_DIR", "data/ground_truth"))
    runs_dir = out / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in seeds:
        match_id = ensure_match(seed, data_dir, gt_dir)
        run = await run_match(data_dir / match_id, "eval", settings)
        (runs_dir / f"{match_id}.json").write_text(json.dumps(run, indent=1, ensure_ascii=False))
        runs.append(run)
        u = run["usage"]
        print(
            f"{match_id}: {run['candidates']} candidates, {run['status_counts']}, "
            f"{u['cost_eur']:.4f} EUR",
            flush=True,
        )
        if run["budget_stopped"]:
            print(f"STOPPED: {run['budget_stopped']}")
            break
    report = {
        "set": name,
        "seeds": seeds,
        "provider": settings.provider,
        "models": runs[0]["models"] if runs else None,
        **score(runs, data_dir, gt_dir),
    }
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    title = "Evaluation report" if name == "official" else "Dev report"
    (out / "report.html").write_text(render_html(report, title))
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval.run_eval")
    ap.add_argument("--set", choices=list(SETS), required=True)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    seeds, out = SETS[a.set]
    if a.set == "official" and (out / "report.json").exists():
        print(f"{out / 'report.json'} exists: the official evaluation runs once.")
        return 1
    settings = Settings()
    if a.set == "official" and settings.provider == "fake":
        print("the official evaluation needs a real provider (MODEL_PROVIDER=foundry)")
        return 1
    print(f"provider {settings.provider}: {settings.model_fast} / {settings.model_reasoning}")
    if a.set == "dev" and out.exists():
        shutil.rmtree(out)
    report = asyncio.run(run_set(a.set, seeds, out, settings))
    print(json.dumps({k: v for k, v in report.items() if k not in ("matches", "seeds")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
