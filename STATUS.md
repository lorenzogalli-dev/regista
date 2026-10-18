# Status

Last updated: 2026-10-18. This file can drift: check the real state (run it, query it) before trusting it.

## Done
- D0 skeleton (2026-10-17): repo layout, uv project, ruff/mypy/pytest, FastAPI `/health` with DB check, Docker Compose (PostgreSQL 17 + API), Vite/React/TS scaffold with `/graphics` placeholder, CI, MIT licence.
- D1 simulator + replay:
  - `sim generate` (events + 10 Hz tracking, gzip), 5 storyline types as parameter modifiers, control seeds, ground truth written to a separate tree.
  - Replay over WebSocket (`/ws/replay/{match_id}?speed=&from_ms=`), frame decimation at high speed, `sim watch` terminal client.
  - Timing: ~3.5 s simulate + ~2.2 s write per full match (macOS ARM).

## In progress
- D4 evaluation done (2026-10-18): official run once on 20 eval + 10 control seeds (`docs/eval/`): recall 52 %, evidence validity 100 %, 0 unsupported of 81 approved, precision 43 %, precision@3 48 %, 1.8 approved per control match (all evidence-backed), Verifier rejections 15 %, candidate → approval p50 9.5 s.
- D2.0 storyline signal check done (2026-10-18), official table in `docs/signal_check.md`.
  - Three strengthening rounds tuned on 2000–2099; first judged run on 2100–2199 (`docs/signal_check_2100.md`, superseded).
  - Criterion changed after that run (approved): robust z (median/MAD) for all types; official check run once on the final simulator, seeds 2300–2399 (noise holdout 2400–2449).
  - Active: pressing_spell, momentum_shift, tactical_switch (long_ball, wide). player_arc active as **difficult** (2-min slice z 2.44). **Disabled**: fatigue_drop (detected 48 %). `sim/storylines.py: ACTIVE_TYPES, DIFFICULT_TYPES`.
- D2.1 metrics engine + tools done (2026-10-18):
  - shared per-event counters (`metrics/counters.py`) used by minute bins and the live store;
  - fitted on calibration seeds 2000–2199: pass difficulty (AUC 0.715), xG (AUC 0.804), xT 12×8, control-index references (`metrics/params.json`);
  - `MatchStore` (incremental, no look-ahead), physical metrics skipping the half-time reset and data jumps, sprints ≥ 1 s, tier-0 triggers;
  - typed tools + MCP server at `/mcp/` (mcp 1.30, compatible with Agent Framework), ground-truth isolation tests;
  - `metrics summary`, performance at 20×: 0.087 ms per frame p50 vs 5 ms budget (`docs/performance.md`).
- D5a design system + hero frame (2026-10-18), awaiting Lore's screenshot review (`docs/design/`):
  - tokens, self-hosted Archivo/Inter (OFL), `motion` 14.3.0; one shared pitch→screen projection for canvas and DOM;
  - scorebug, player tags, pass trail + pass card (tier 0), AI moment card with verified seal (tier 1) on a recorded clip of m_1000 (`metrics.export_sample`), `/graphics` transparent output, `/design` reference page;
  - team palettes enforce text contrast ≥ 4.5, marks ≥ 3 on the background, home/away separation and distance from the AI cyan (tested on 6 kit pairs);
  - `web/scripts/capture.mjs`: real-time screenshots, video (ffmpeg) and a design audit (title-safe, overlaps, contrast, tabular figures, skew).
- D3 agents + orchestration in progress (2026-10-18), with the fake client:
  - candidate finder in code (2-signal rule, robust z vs noise fitted on 2200-2249): 4.1 candidates per no-storyline match, 5.2 per dev match; on dev seeds 62 % of storylines get a candidate of the right kind in their window (80 % of any kind for the right team);
  - Agent Framework graph workflow Detector → Analyst ⇄ Verifier (hybrid, one retry) → Narrator · Persona · Director → Publish, timeouts and template fallbacks; Analyst tools over MCP (in-process server on the live store);
  - meter + per-run budget cap, cost estimate from real prompt sizes (`agents.estimate`), runs saved as JSON and to PostgreSQL;
  - Foundry deployments created (`gtf-fast`, `gtf-reasoning`); smoke test and four prompt rounds on dev seeds done (spend table below).
  - Dev results (round 4, eval mode): held-out dev 1010-1019 recall 52 % (strict 52 %), precision 41 %, evidence validity 100 % (independent minute-bin check), Verifier rejection 9 %; Analyst p50 6.9 s, Detector 1.2 s.
  - Limits found: ~25 % of storylines get no candidate (mostly player arcs); about half of approved explanations describe ordinary fluctuations the code cannot separate from storylines (same z, same persistence). Further prompt rounds stopped for diminishing returns.
  - Derived texts (captions, 9 personas) are checked by code against the verified claim (numbers and names); failures fall back to templates.

## Foundry spend (estimate vs actual)
Cumulative cap 8 EUR (ledger `data/runs/foundry_ledger.jsonl`, local). Prices: Azure Retail Prices API, EUR.

| Date | Run | Estimate (EUR) | Actual (EUR) | Note |
|---|---|---|---|---|
| 2026-10-18 | Smoke test, 2 calls | < 0.001 | 0.0005 | auth, SDK, structured output OK |
| 2026-10-18 | Dev round 1: 10 dev matches, eval mode, 52 candidates | 0.38 (0.27–0.57) | 0.165 | recall 70 %, precision 27.5 % |
| 2026-10-18 | Dev round 2: team episodes + profile, 31 candidates | 0.25 (0.17–0.37) | 0.117 | recall 50 %, precision 41.7 % (Verifier too strict, wide dropped) |
| 2026-10-18 | Dev round 3: looser Verifier, fired kinds | 0.25 (0.18–0.38) | 0.139 | recall 50 %, precision 35.7 % (player names not mapped to ids) |
| 2026-10-18 | Dev round 4: names → ids, Detector keeps player arcs; 20 dev matches (1000-1019) | 0.53 (0.37–0.80) | 0.268 | tuning 1000-1009: recall 65 %, precision 48 %; held-out 1010-1019: recall 52 %, precision 41 % |
| 2026-10-18 | Full pipeline, 3 dev matches (captions, personas, Director) | 0.16 (0.11–0.24) | 0.070 | persona invented a scorer; texts cut by schema limits |
| 2026-10-18 | Full pipeline after text check + glossary, same 3 matches | ~0.07 (from previous actual) | 0.073 | no invented facts, no cut texts |
| 2026-10-18 | Dev report, final config, 20 dev matches | 0.53 | 0.281 | recall 51 %, precision 38 %, P@3 44 %, 0 unsupported |
| 2026-10-18 | **Official eval**, 20 eval + 10 control, once | 0.73 (0.51–1.09) | 0.385 | see README / docs/eval |
| | **Cumulative** | | **1.50** | cap 8 EUR |

## Blocked
- Nothing.

## Open checks
- Cross-platform determinism: the `simulator-crossplatform` CI job compares Linux output for seed 1000 with the digest recorded on macOS ARM (`tests/data/digest_m_1000.json`).
  - 2026-10-17, commit 77dc973: **match** on GitHub `ubuntu-latest` (Ubuntu 24.04, CPython 3.12.3, numpy 2.5.4) vs macOS arm64 (CPython 3.12.7). One seed only; re-check whenever numpy or Python changes.
  - 2026-10-18, commit 78d8c4b (after D2.0 simulator changes): events.jsonl and match.json **identical** on Linux; tracking frames sampled every 30 s identical (max abs difference 0.000); the full tracking file differs (some values differ in the last decimal). Treated as a known difference: exact tracking equality is an `xfail(strict=False)` test, events must match exactly.
  - 2026-10-18, commit 3af8a07 (final simulator): full tracking file **identical** on Linux too (the xfail passed). Kept non-strict: one seed only.

## Decisions
- GitHub Models was retired on 2026-07-30 (its endpoint now answers "OK" to any request); development uses the fake client, Foundry only for prompt tuning, eval and recorded runs, each after a cost estimate. Hackathon Azure budget: 10 EUR.
- Models (final, 2026-10-18): `gtf-fast` = gpt-5.4-mini (Data Zone Standard, 20K TPM) for Detector, Verifier, Narrator, Persona, Director; `gtf-reasoning` = gpt-5-mini (Global Standard, 20K TPM, low reasoning effort) for the Analyst. GPT-6 / GPT-5.6 quota is not available for this subscription (0 TPM in every region). Foundry resource `gtf-foundry`, Italy North. Prices (Azure Retail Prices API, EUR per 1M tokens): gpt-5.4-mini 0.726 in / 4.356 out; gpt-5-mini 0.22 in / 1.76 out.
- Eval: full sample, 20 eval + 10 control seeds, run once. Foundry spend capped at 8 EUR cumulative (ledger in `data/runs/foundry_ledger.jsonl`, enforced by `agents.run`).
- mcp pinned to 1.x (`>=1.30,<2`): agent-framework-core 1.22 requires `mcp<2` for its MCP tools; mcp 2.x renamed FastMCP and changed APIs.
- Difficult-pass trigger: SPEC suggested difficulty > 0.8, but difficulty is P(pass fails), and completed passes almost never reach 0.8; the threshold is the 98th percentile of completed calibration passes (0.491).
- Speed trigger at most once per player per 5 minutes (at 60 s there were ~135 a match).
- Control index components: team mean possession length, turnovers/min, event-rate variability (30 s buckets), share of team possessions ending in the opponent half; each through a logistic around the calibration median.
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
- Plausibility (20 dev seeds, 2026-10-18, final simulator): means passes 997, completion 0.796 (min 0.726), shots 28.5 (18–42), goals 1.85 (0–6), tackles 46.5 (31–68), max speed 9.90 m/s. Per-match bands: shots 10–45, goals 0–7, tackles 25–80; tackle mean 35–55.
- Realism (20 dev seeds, full-match players, per 90): distance DEF 8.8 / MID 10.3 / FWD 10.7 km (FWD was 11.6–12.4; forwards now reposition off the ball more slowly, max 14.0 for a few); sprints DEF 12 / MID 9 / FWD 19; touches DEF 33 / MID 79 / FWD 67.
- Touches use the event-data convention (on-ball actions: pass, shot, tackle, interception, clearance, ball recovery); receptions and carries are not separate touches. The old definition gave ~200 per midfielder. Field tilt and flank shares count final-third passes, carries and shots ("ball actions"). Remaining gap: defenders touch the ball less and forwards more than in real football.
- Game management: a team leading by 2 shoots half as often, by 3+ a tenth as often (caps goal tails).
- A red-card storyline player is protected from substitution until the card.
