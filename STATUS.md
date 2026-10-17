# Status

Last updated: 2026-10-17. This file can drift: check the real state (run it, query it) before trusting it.

## Done
- D0 skeleton: repo layout, uv project, ruff/mypy/pytest, FastAPI `/health` with DB check, Docker Compose (PostgreSQL 17 + API), Vite/React/TS web scaffold with `/graphics` placeholder, CI workflow, MIT licence.

## In progress
- D1 simulator + replay (next).

## Blocked
- Nothing.

## Decisions
- Spec changes approved on 2026-10-17 (see SPEC.md): two overlay tiers, hybrid Verifier, metrics tools behind an MCP server, forced trigger for `momentum_shift`, 2–3 non-overlapping storylines per match, control seeds, revised eval metrics, xG/xT calibrated on the simulator, `duel` cut, single Container App, Burstable PostgreSQL, live daily model-call cap, recorded runs are real pipeline outputs.
- Front-end is governed by DESIGN.md; D5 split into D5a (after D2) and D5b (after D3/D4).
- Personas: analyst / casual / player_focus × en / it / es.
- Agent Framework packages: `agent-framework-core` + `agent-framework-foundry` (not the `agent-framework` meta-package). Versions re-checked before D3.
- TypeScript: version pinned by the Vite template (`~6.0.2`); linter is the template's oxlint.
- Postgres access: psycopg 3 + plain SQL, idempotent `schema.sql` applied at startup (no ORM, no migrations tool).
- Test client: `httpx2` (Starlette deprecates `httpx` for its TestClient).
- `data/ground_truth/` is git-ignored and never mounted into the API container.
