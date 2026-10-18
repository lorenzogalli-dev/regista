"""Save a pipeline run to PostgreSQL (runs + run_moments). Plain SQL, psycopg 3."""

import json
from typing import Any

import psycopg

from api.db import SCHEMA_PATH


def save_run(url: str, run: dict[str, Any]) -> None:
    summary = {k: v for k, v in run.items() if k not in ("moments", "calls")}
    seed = int(run["match_id"].removeprefix("m_"))
    with psycopg.connect(url, connect_timeout=5) as conn:
        conn.execute(SCHEMA_PATH.read_text())
        conn.execute(
            """INSERT INTO runs (run_id, match_id, seed, mode, finished_at, provider,
                                 pipeline_mode, cost_eur, summary)
               VALUES (%s, %s, %s, 'recorded', now(), %s, %s, %s, %s)""",
            (
                run["run_id"],
                run["match_id"],
                seed,
                run["provider"],
                run["mode"],
                run["usage"]["cost_eur"],
                json.dumps(summary),
            ),
        )
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO run_moments (run_id, moment_id, t_ms, status, data)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (
                        run["run_id"],
                        m["moment_id"],
                        m["candidate"]["t_ms"],
                        m["status"],
                        json.dumps(m),
                    )
                    for m in run["moments"]
                ],
            )
