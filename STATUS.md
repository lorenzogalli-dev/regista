# Status

Last updated: 2026-10-17. This file can drift: check the real state (run it, query it) before trusting it.

## Done
- D0 skeleton (2026-10-17): repo layout, uv project, ruff/mypy/pytest, FastAPI `/health` with DB check, Docker Compose (PostgreSQL 17 + API), Vite/React/TS scaffold with `/graphics` placeholder, CI, MIT licence.
- D1 simulator + replay:
  - `sim generate` (events + 10 Hz tracking, gzip), 5 storyline types as parameter modifiers, control seeds, ground truth written to a separate tree.
  - Replay over WebSocket (`/ws/replay/{match_id}?speed=&from_ms=`), frame decimation at high speed, `sim watch` terminal client.
  - Timing: ~3.5 s simulate + ~2.2 s write per full match (macOS ARM).

## In progress
- D2 metrics engine + tools API (next).

## Blocked
- Nothing.

## Open checks
- Cross-platform determinism: the `simulator-crossplatform` CI job compares Linux output for seed 1000 with the digest recorded on macOS ARM (`tests/data/digest_m_1000.json`). Result: see below once CI has run.

## Decisions
- Spec changes approved on 2026-10-17 (see SPEC.md): two overlay tiers, hybrid Verifier, metrics tools behind an MCP server, forced trigger for `momentum_shift`, 2–3 non-overlapping storylines per match, control seeds, revised eval metrics, xG/xT calibrated on the simulator, `duel` cut, single Container App, Burstable PostgreSQL, live daily model-call cap, recorded runs are real pipeline outputs.
- Front-end is governed by DESIGN.md; D5 split into D5a (after D2) and D5b (after D3/D4).
- Personas: analyst / casual / player_focus × en / it / es.
- Agent Framework packages: `agent-framework-core` + `agent-framework-foundry` (not the meta-package). Versions re-checked before D3.
- TypeScript: version pinned by the Vite template (`~6.0.2`); linter is the template's oxlint.
- Postgres access: psycopg 3 + plain SQL, idempotent `schema.sql` at startup.
- Test client: `httpx2` (Starlette's documented TestClient backend; provenance checked 2026-10-17).
- `data/ground_truth/` is git-ignored and never mounted into the API container.
- Demo matches and recorded agent runs are generated once and kept as artefacts (location decided in D6); they are never regenerated inside Docker builds.
- Simulator details:
  - Shot outcomes use `goal | saved | off_target | blocked`; saves `won | parried` (parry → corner).
  - Events do not carry `xg`: xG belongs to the metrics engine (D2), fitted on synthetic shots.
  - `momentum_shift` triggers are a red card or an impact substitution (not a forced goal). Scheduled actions wait for the ball to land, so they can fire a few seconds after the window start.
  - `fatigue_drop` ends with the tiring player's substitution; `player_arc` is a "playmaker" spell; `tactical_switch` is `long_ball` or `wide`.
  - Players teleport to kickoff positions at the start of each half (velocity reset); metrics must not count that jump as distance.
  - Sprint counting needs a minimum duration (≥ 1 s): instantaneous speed jitters around thresholds.
- Plausibility (20 dev seeds, 2026-10-17, after the tackle fix): means passes 1012, completion 0.814, shots 24.5, goals 2.45, max player speed 9.90 m/s, tackles 42.5 (range 29–54). Per-match shot band widened from the proposed 14–36 to 10–45 (approved). Tackles: mean must be 35–55, per-match band 25–80 (match-to-match variance is driven by how often defenders get close). Fewer tackles are offset by loose balls when a carrier is squeezed (`ball_recovery`); fouls are now 33% of tackle attempts (~15–25 per match).
