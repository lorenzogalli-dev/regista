"""Download the demo data (public match files and recorded runs) from Azure Blob Storage at
startup. Read-only, with the container app's managed identity; no keys.

Blob layout under DATA_BLOB_URL (https://<account>.blob.core.windows.net/<container>):
    generated/m_1000/match.json, events.jsonl, tracking.jsonl.gz, tracking.idx.json
                                                                   -> MATCH_DATA_DIR
    recorded/r_m_1000_xxxxxxxx.json                                -> RUNS_DIR

Only an allowlist of public files is accepted (infra/upload_data.py applies the same list);
any other blob stops the startup.
"""

import logging
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

log = logging.getLogger(__name__)
API_VERSION = "2023-11-03"
PREFIXES = {"generated/": "MATCH_DATA_DIR", "recorded/": "RUNS_DIR"}


ALLOWED = re.compile(
    r"^(generated/m_\d{1,9}/(match\.json|events\.jsonl|tracking\.jsonl\.gz|tracking\.idx\.json)"
    r"|recorded/r_m_\d{1,9}_[0-9a-f]{8}\.json)$"
)


class UnexpectedBlob(RuntimeError):
    pass


def check_name(name: str) -> None:
    """Only public match files and recorded runs; anything else is refused."""
    if not ALLOWED.match(name):
        raise UnexpectedBlob(f"refusing blob {name!r}")


def _token() -> str:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token("https://storage.azure.com/.default").token


def _get(url: str, token: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "x-ms-version": API_VERSION}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data: bytes = r.read()
        return data


def list_blobs(base: str, token: str) -> list[str]:
    names: list[str] = []
    marker = ""
    while True:
        xml = _get(f"{base}?restype=container&comp=list&marker={marker}", token)
        root = ET.fromstring(xml)
        names += [b.findtext("Name") or "" for b in root.iter("Blob")]
        marker = root.findtext("NextMarker") or ""
        if not marker:
            return names


def sync(base: str | None = None) -> int:
    """Download every blob to its local directory; returns the number of files written."""
    base = (base or os.environ.get("DATA_BLOB_URL", "")).rstrip("/")
    if not base:
        return 0
    token = _token()
    n = 0
    for name in list_blobs(base, token):
        check_name(name)
        prefix = next(p for p in PREFIXES if name.startswith(p))
        root = Path(os.environ.get(PREFIXES[prefix], f"data/{prefix.rstrip('/')}"))
        dest = root / name[len(prefix) :]
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_get(f"{base}/{name}", token))
        n += 1
    log.info("data sync: %d files from %s", n, base)
    return n
