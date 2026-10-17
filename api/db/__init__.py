"""PostgreSQL access. Plain SQL over psycopg 3; the schema is applied idempotently at startup."""

import logging
import os
from pathlib import Path

import psycopg

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


async def ping() -> bool:
    url = database_url()
    if not url:
        return False
    try:
        async with await psycopg.AsyncConnection.connect(url, connect_timeout=3) as conn:
            await conn.execute("SELECT 1")
        return True
    except psycopg.Error as exc:
        log.warning("database ping failed: %s", exc)
        return False


async def apply_schema() -> None:
    url = database_url()
    if not url:
        log.warning("DATABASE_URL not set; skipping schema")
        return
    try:
        async with await psycopg.AsyncConnection.connect(url, connect_timeout=3) as conn:
            await conn.execute(SCHEMA_PATH.read_text())
    except psycopg.Error as exc:
        # The API still starts; /health reports the database as unreachable.
        log.error("could not apply schema: %s", exc)
