"""Cumulative spend ledger for real model calls (one JSON line per run, local, git-ignored).

`agents.run` refuses calls once the ledger total plus the current run reaches
FOUNDRY_TOTAL_CAP_EUR; every run that used a real provider appends its measured cost.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def path() -> Path:
    return Path(os.environ.get("FOUNDRY_LEDGER", "data/runs/foundry_ledger.jsonl"))


def spent() -> float:
    p = path()
    if not p.exists():
        return 0.0
    return float(
        sum(json.loads(line)["cost_eur"] for line in p.read_text().splitlines() if line.strip())
    )


def record(entry: dict[str, Any]) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), **entry}
    with p.open("a") as f:
        f.write(json.dumps(row) + "\n")
