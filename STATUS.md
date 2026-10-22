# Status

Last updated: 2026-10-22. This file can drift: check the real state (run it, query it) before trusting it.

## State (2026-10-22)
All deliverables D0–D6 are done. After D6: UX/design revision and rename to **Regista** (see Done), then a pre-submission audit and cleanup (2026-10-22). Live demo: https://gtf-app.delightfulbush-9c2f92ce.italynorth.azurecontainerapps.io (start at `/tour`). The app stays up until 10 Nov 2026; from 11 Nov `infra/post_judging.sh` deletes PostgreSQL and scales the app to 0 (it refuses to run earlier unless `FORCE=1`).

Operations:
- Redeploy: push to `main` → CI → `image` workflow pushes `ghcr.io/lorenzogalli-dev/regista:<full sha>` (the package name follows the repo name) → `az containerapp update -n gtf-app -g <rg> --image <that tag>` (or `PHASE=app infra/deploy.sh`). Resource names and endpoints live in `.env` / `.deploy.secrets` (local, not committed). Production runs image `regista:365d7da…` (revision `gtf-app--0000005`, 2026-10-22); the package `regista` is public.
- Container App `gtf-app`: 0.25 vCPU / 0.5 GiB, 1 replica (load test: ~125 MB RSS, ~3 % CPU). System-assigned identity with *Storage Blob Data Reader* and *Cognitive Services User* (*Cognitive Services OpenAI User* gave 403 on the Foundry project endpoint; the granted role also allows listing keys).
- At startup the app downloads demo data from Blob through an allowlist (`api/data_sync.py`); ground truth is never uploaded (`infra/upload_data.py`, tested).
- Live sessions spend Foundry credit: cap 150 model calls/day (`/api/live/quota`). PostgreSQL B1ms bills ~0.0175 EUR/h while it exists.
- Eval seeds 5000–5019 / 9000–9009 and signal-check seeds 2300–2449 are used: do not re-run the official evaluations.

## Done
- D0 skeleton (2026-10-17): repo layout, uv project, ruff/mypy/pytest, FastAPI `/health` with DB check, Docker Compose, Vite/React/TS scaffold, CI, MIT licence.
- D1 simulator + replay: `sim generate` (events + 10 Hz tracking), storylines as parameter modifiers, control seeds, ground truth in a separate tree; replay over WebSocket. ~3.5 s simulate + ~2.2 s write per match.
- D2.0 storyline signal check (official table `docs/signal_check.md`):
  - Three strengthening rounds tuned on 2000–2099; first judged run on 2100–2199 (`docs/signal_check_2100.md`, superseded).
  - Criterion changed after that run (approved): robust z (median/MAD) for all types; official check run once on seeds 2300–2399 (noise holdout 2400–2449).
  - Active: pressing_spell, momentum_shift, tactical_switch (long_ball, wide); player_arc active as **difficult**; **disabled**: fatigue_drop (48 %). `sim/storylines.py: ACTIVE_TYPES, DIFFICULT_TYPES`.
- D2.1 metrics engine + tools: shared counters, pass difficulty (AUC 0.715), xG (AUC 0.804), xT 12×8, control index (`metrics/params.json`); incremental `MatchStore`; typed tools + MCP server at `/mcp/` with ground-truth isolation tests; 0.087 ms per frame p50 at 20× (`docs/performance.md`).
- D3 agents + orchestration: candidate finder in code (2-signal rule, robust z vs noise); Agent Framework graph Detector → Analyst ⇄ Verifier (hybrid, one retry) → Narrator · Persona · Director → Publish, with timeouts and template fallbacks; Analyst tools over MCP; derived texts checked by code; per-run budget and cumulative cap; runs saved as JSON and to PostgreSQL. Known limits: ~25 % of storylines get no candidate (mostly player arcs); about half of approved explanations describe ordinary fluctuations with the same signature as storylines.
- D4 evaluation, official run once on 20 eval + 10 control seeds (`docs/eval/`): recall 52 %, 0 unsupported of 81 approved, evidence validity 100 % of 267 recomputed items (45 not independently recomputable), precision 43 %, precision@3 48 %, 1.8 approved per control match, Verifier rejections 15 %, Analyst p50 6.8 s, cost 0.385 EUR.
- D5a design system + hero frame (`docs/design/archive/d5a/`): tokens, self-hosted OFL fonts, `motion` 14.3.0, shared pitch→screen projection, team palettes with contrast rules, `web/scripts/capture.mjs` (screenshots, video, design audit).
- D5b views on real recorded runs (`data/recorded/`, `docs/design/archive/d5b/`): broadcast (template → verified card), split view, control room with an authentic Verifier rejection (run r_m_5016, provenance shown), /graphics, eval page, landing, second screen, recap; recorded and live share one WebSocket vocabulary.
- D6 (2026-10-18): Azure Container Apps + PostgreSQL + Blob + App Insights. Verified in production: `/health` with DB, Blob data sync (4 runs), eval report, live quota, 404 on ground-truth / traversal / unknown paths, every front-end route, recorded WebSocket, external MCP (6 tools, traversal refused), one live moment published end to end on Foundry via managed identity, App Insights spans from Agent Framework, design audit clean. Final README, demo clips and voice-over.

- UX/design revision + rename (2026-10-18, after D6): project renamed **Regista** ("Reads the game. Directs the broadcast."; Azure resources keep their `gtf-*` names). Guided tour `/tour` (≈ 2 min) as the landing's main action; new landing (problem, what it does, trust schema, results with caveats, explore, under the hood); broadcast player with clickable timeline (tier 0 / tier 1 lanes, goals, shots, red cards, Verifier rejections), next key moment (N), auto-skip of quiet play (×8), moment replay (slow, hold for reading time, Space continues), telestration from match data (`metrics/telestration.py`, `/api/runs/{id}/timeline`), insights feed, evidence panel behind the ✓ seal; control-room tokens moving through the agent graph. Recorded WebSocket accepts `{"type":"pace","speed":…}` (pause, fast-forward, hold). Type: Barlow Condensed / Barlow / Newsreader (OFL, self-hosted); accent green `#7CF25C`. Layout audit `web/scripts/audit.sh` (21 audits at 1920/1440/390, no problems); review material `docs/design/regista/`; demo clips and voice-over rebuilt around the tour. No model calls (recorded runs only).
- Logo (2026-10-19): icon and wordmark drawn by hand in this repo (`docs/brand/`); every file in the history checked against other products' public icons and colours: no match. Served as `/regista-icon.svg`.
- Production verified on 2026-10-19 (revision `gtf-app--0000003`): `/health` ok with DB; every route incl. `/tour` 200; new icon and fonts served; `/api/runs/{id}/timeline` 200; ground truth, traversal and unknown paths 404; MCP server answers as `regista-metrics`; layout audit (`web/scripts/audit.sh` with `BASE` = production): the audits that completed (player with telestration, insights, timeline) found no layout problem, but the full run was stopped; its fixed `auditAt` delays are tuned on the laptop and fire too early in production (see Open checks).
- Site pages restyle (2026-10-22): landing, eval report, architecture and recap get a centred pill nav, full-width bands alternating dark grey and chalk, stadium-scoreboard numbers, tactics-board links and shirt-number steps (`web/src/routes/site.css`, DESIGN.md §5c); architecture diagram text no longer overlaps or clips. Broadcast, tour, split and control room unchanged (layout audit: 21 audits, no problems). Clips 01, 10, 11 and the landing screenshots retaken.
- Pre-submission audit (2026-10-22): no secrets in the full history (gitleaks, trufflehog, real values); no third-party material; production `gtf-app--0000004` verified from a clean browser (every page and tour step; ground truth, traversal and `.env` 404); a fresh clone following the README runs the recorded runs and the tour, and generates byte-identical matches.

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
| 2026-10-18 | Recorded demo runs, full pipeline, m_1000 / m_1003 / m_1009 | 0.27 (0.19–0.41) | 0.133 | first take (generic persona headlines) |
| 2026-10-18 | Recorded demo runs again, specific persona headlines | 0.27 (0.19–0.41) | 0.115 | kept in data/recorded |
| 2026-10-18 | Production live-session check (6 calls, not in the local ledger) | – | ~0.01 | managed identity works |
| | **Cumulative** | | **~1.76** | cap 8 EUR |

## Blocked
- Nothing.

## Open checks
- **Seek latency in production** (0.25 vCPU), time to first frame on `/ws/recorded/…` for the tour steps: before (rev. 3) → seek index (rev. 4) → history in one `events` message (rev. 5, 2026-10-22, three runs): 33:51 2.56 → 0.45 → 0.23–0.29 s; 35:31 2.66 → 0.51 → 0.22–0.32 s; 33:57 2.70 → 0.40 → 0.22–0.29 s; 34:11 2.58 → 0.41 → 0.20–0.31 s; 81:38 5.80 → 1.00–1.09 → 0.35–0.47 s; 85:48 (control room) 6.25 → 1.02–1.09 → 0.43–0.80 s. Tour steps start their clock at the first frame. Resolved.
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
- Rename to Regista (2026-10-18): UI, docs, package (`pyproject`), MCP server name, telemetry service name, GitHub repo and GHCR image; Azure resource names (`gtf-*`) unchanged (internal).
- Telestration is code, not a model: shapes and counts come from public match events in the evidence window; it uses the brand green ("from the data"), never the AI cyan.
- Landing results say recall 52 % on **20** unseen evaluation matches (the 10 control matches have no storylines and are reported separately).
- Personas: analyst / casual / player_focus × en / it / es.
- Agent Framework packages: `agent-framework-core` + `agent-framework-foundry` (not the meta-package). Versions re-checked before D3.
- TypeScript: version pinned by the Vite template (`~6.0.2`); linter is the template's oxlint.
- Postgres access: psycopg 3 + plain SQL, idempotent `schema.sql` at startup.
- Test client: `httpx2` (Starlette's documented TestClient backend; provenance checked 2026-10-17).
- `data/ground_truth/` is git-ignored and never mounted into the API container.
- Demo matches and recorded agent runs are generated once and kept as artefacts (Blob Storage in production, `data/recorded/` in the repo); they are never regenerated inside Docker builds.
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
