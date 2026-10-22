"""Upload the demo data to Azure Blob Storage: public files of the matches that recorded runs
use, and the recorded runs. Every name passes the same allowlist the API applies at startup
(api.data_sync.check_name), so nothing else (in particular no ground truth) can be uploaded.

    uv run python infra/upload_data.py <storage-account> <container> [--dry-run]

Uses `az storage blob upload` with your Azure CLI login (role: Storage Blob Data Contributor).
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from api.data_sync import check_name

MATCH_FILES = ("match.json", "events.jsonl", "tracking.jsonl.gz", "tracking.idx.json")


def manifest(runs_dir: Path, data_dir: Path) -> list[tuple[str, Path]]:
    """(blob name, local file) for every recorded run and the match files it needs."""
    out: list[tuple[str, Path]] = []
    matches: set[str] = set()
    for p in sorted(runs_dir.glob("r_m_*.json")):
        out.append((f"recorded/{p.name}", p))
        matches.add(json.loads(p.read_text())["match_id"])
    for m in sorted(matches):
        for f in MATCH_FILES:
            out.append((f"generated/{m}/{f}", data_dir / m / f))
    for name, path in out:
        check_name(name)
        if not path.is_file():
            raise FileNotFoundError(path)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("account")
    ap.add_argument("container")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    files = manifest(
        Path(os.environ.get("RUNS_DIR", "data/recorded")),
        Path(os.environ.get("MATCH_DATA_DIR", "data/generated")),
    )
    for name, path in files:
        print(f"{name}  ({path.stat().st_size / 1e6:.1f} MB)")
        if a.dry_run:
            continue
        subprocess.run(
            [
                "az",
                "storage",
                "blob",
                "upload",
                "--auth-mode",
                "login",
                "--overwrite",
                "--account-name",
                a.account,
                "--container-name",
                a.container,
                "--name",
                name,
                "--file",
                str(path),
                "--only-show-errors",
                "--output",
                "none",
            ],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
