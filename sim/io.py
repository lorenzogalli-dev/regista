"""Deterministic writers and readers for simulator output.

Layout:
  <out>/match.json, <out>/events.jsonl, <out>/tracking.jsonl.gz, <out>/tracking.idx.json
  <gt_dir>/<match_id>/storylines.json   (hidden ground truth, separate tree)

tracking.jsonl.gz holds one gzip member per match minute (still a plain gzip file to any
reader); tracking.idx.json gives each member's first t_ms and byte offset, so a replay that
starts late in the match decompresses one minute instead of everything before it.
"""

import contextlib
import gzip
import hashlib
import json
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import IO, Any

from sim.engine import SimResult
from sim.schema import GroundTruth, MatchMeta

MATCH_FILE = "match.json"
EVENTS_FILE = "events.jsonl"
TRACKING_FILE = "tracking.jsonl.gz"
INDEX_FILE = "tracking.idx.json"
GT_FILE = "storylines.json"
MEMBER_MS = 60_000
_T_MS = re.compile(rb'^\{"t_ms":(\d+),')


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
    write_tracking((line.encode() for line in tracking_lines(result)), out_dir)
    paths["index"] = out_dir / INDEX_FILE
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


def _t_ms(line: bytes) -> int:
    m = _T_MS.match(line)
    if m is None:
        raise ValueError(f"tracking line without a leading t_ms: {line[:40]!r}")
    return int(m.group(1))


def write_tracking(lines: Iterable[bytes], out_dir: Path) -> None:
    """Write tracking lines as one deterministic gzip member per match minute, and the index."""
    members: list[list[int]] = []
    with (out_dir / TRACKING_FILE).open("wb") as raw:
        gz: gzip.GzipFile | None = None
        minute = -1
        for line in lines:
            t = _t_ms(line)
            if t // MEMBER_MS != minute:
                if gz is not None:
                    gz.close()
                minute = t // MEMBER_MS
                members.append([t, raw.tell()])
                gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6)
            assert gz is not None
            gz.write(line)
        if gz is not None:
            gz.close()
        size = raw.tell()
    index = {"member_ms": MEMBER_MS, "size": size, "members": members}
    (out_dir / INDEX_FILE).write_text(_dumps(index) + "\n")


def reindex_tracking(match_dir: Path) -> None:
    """Rewrite an existing tracking file in the indexed layout; its content does not change."""
    before = content_digest(match_dir)["tracking.jsonl"]
    tmp = match_dir / ".reindex"
    tmp.mkdir(exist_ok=True)
    with gzip.open(match_dir / TRACKING_FILE, "rb") as f:
        write_tracking(f, tmp)
    (tmp / TRACKING_FILE).replace(match_dir / TRACKING_FILE)
    (tmp / INDEX_FILE).replace(match_dir / INDEX_FILE)
    tmp.rmdir()
    if content_digest(match_dir)["tracking.jsonl"] != before:
        raise RuntimeError(f"reindexing changed the tracking content of {match_dir}")


def _seek_offset(match_dir: Path, from_ms: int) -> int:
    """Byte offset of the member holding `from_ms`; 0 without a valid index."""
    path = match_dir / INDEX_FILE
    if from_ms <= 0 or not path.is_file():
        return 0
    index = json.loads(path.read_text())
    if index.get("size") != (match_dir / TRACKING_FILE).stat().st_size:
        return 0  # stale index: the tracking file was replaced without it
    offset = 0
    for first_t, off in index["members"]:
        if first_t > from_ms:
            break
        offset = off
    return int(offset)


def iter_tracking(match_dir: Path, from_ms: int = 0) -> Iterator[dict[str, Any]]:
    """Tracking frames in time order; with `from_ms`, only frames at or after it."""
    with contextlib.ExitStack() as stack:
        raw: IO[bytes] = stack.enter_context((match_dir / TRACKING_FILE).open("rb"))
        raw.seek(_seek_offset(match_dir, from_ms))
        f = stack.enter_context(gzip.GzipFile(fileobj=raw, mode="rb"))
        for line in f:
            if from_ms and _t_ms(line) < from_ms:
                continue
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
