"""Deterministic writers and readers for simulator output.

Layout:
  <out>/match.json, <out>/events.jsonl, <out>/tracking.jsonl.gz
  <gt_dir>/<match_id>/storylines.json   (hidden ground truth, separate tree)
"""

import gzip
import hashlib
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sim.engine import SimResult
from sim.schema import GroundTruth, MatchMeta

MATCH_FILE = "match.json"
EVENTS_FILE = "events.jsonl"
TRACKING_FILE = "tracking.jsonl.gz"
GT_FILE = "storylines.json"


class GroundTruthLeak(ValueError):
    """Raised when the ground-truth directory would overlap the public output directory."""


def check_separation(out_dir: Path, gt_dir: Path) -> None:
    out, gt = out_dir.resolve(), gt_dir.resolve()
    if out == gt or out.is_relative_to(gt) or gt.is_relative_to(out):
        raise GroundTruthLeak(f"ground truth dir {gt} must not overlap output dir {out}")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def tracking_lines(result: SimResult) -> Iterator[str]:
    ids = [p.player_id for p in result.meta.players]
    for i in range(len(result.t_ms)):
        bx, by, bz, bs = result.ball[i]
        players = ",".join(
            f'{{"player_id":"{ids[k]}","x":{x:.2f},"y":{y:.2f},"speed_ms":{s:.2f}}}'
            for k, (x, y), s in zip(
                result.slot_player[i], result.pos[i], result.speed[i], strict=True
            )
            if k >= 0
        )
        yield (
            f'{{"t_ms":{int(result.t_ms[i])},"period":{int(result.period[i])},'
            f'"ball":{{"x":{bx:.2f},"y":{by:.2f},"z":{bz:.2f},"speed_ms":{bs:.2f}}},'
            f'"players":[{players}]}}\n'
        )


def write_match(result: SimResult, gt: GroundTruth, out_dir: Path, gt_dir: Path) -> dict[str, Path]:
    check_separation(out_dir, gt_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "match": out_dir / MATCH_FILE,
        "events": out_dir / EVENTS_FILE,
        "tracking": out_dir / TRACKING_FILE,
    }
    paths["match"].write_text(result.meta.model_dump_json(indent=2) + "\n")
    with paths["events"].open("w") as f:
        for e in result.events:
            f.write(_dumps(e) + "\n")
    with (
        paths["tracking"].open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as gz,
        io.TextIOWrapper(gz, encoding="utf-8") as f,
    ):
        f.writelines(tracking_lines(result))
    gt_match_dir = gt_dir / result.meta.match_id
    gt_match_dir.mkdir(parents=True, exist_ok=True)
    paths["ground_truth"] = gt_match_dir / GT_FILE
    paths["ground_truth"].write_text(gt.model_dump_json(indent=2) + "\n")
    return paths


def read_meta(match_dir: Path) -> MatchMeta:
    return MatchMeta.model_validate_json((match_dir / MATCH_FILE).read_text())


def iter_events(match_dir: Path) -> Iterator[dict[str, Any]]:
    with (match_dir / EVENTS_FILE).open() as f:
        for line in f:
            yield json.loads(line)


def iter_tracking(match_dir: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(match_dir / TRACKING_FILE, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def content_digest(match_dir: Path) -> dict[str, str]:
    """sha256 of each public file's *uncompressed* content (independent of the zlib build)."""
    out = {}
    for name in (MATCH_FILE, EVENTS_FILE):
        out[name] = hashlib.sha256((match_dir / name).read_bytes()).hexdigest()
    h = hashlib.sha256()
    with gzip.open(match_dir / TRACKING_FILE, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    out["tracking.jsonl"] = h.hexdigest()
    return out
