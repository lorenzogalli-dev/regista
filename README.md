# Ground Truth Football

A multi-agent system on Microsoft Foundry that turns a live stream of synthetic football events and tracking into explainable, personalised on-screen intelligence, and measures how often its explanations are right against a hidden ground truth the agents never see.

> Work in progress for the Microsoft × Premier League Hackathon. All data is synthetic; all clubs, players, venues and competitions are fictional.

- Technical spec: [`SPEC.md`](SPEC.md)
- Design direction: [`DESIGN.md`](DESIGN.md)
- Progress: [`STATUS.md`](STATUS.md)

## Run locally

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node 22.

```sh
cp .env.example .env            # optional for now; model settings are needed from D3
docker compose up -d --build    # PostgreSQL + API on :8000
curl localhost:8000/health      # {"status":"ok","db":"ok"}

cd web && npm install && npm run dev   # front-end on :5173, proxies the API
```

## Simulator

```sh
uv run sim generate --seed 1000          # data/generated/m_1000 + data/ground_truth/m_1000 (hidden)
docker compose up -d --build             # API serves data/generated read-only
uv run sim watch m_1000 --speed 20       # terminal client for ws://localhost:8000/ws/replay/m_1000
uv run sim plausibility --set dev        # summary stats over the 20 dev seeds
```

A full 90+ minute match (events + 10 Hz tracking) takes about 6 s to simulate and write on an
Apple-silicon laptop. Seed sets: dev 1000–1019 (tuning), eval 5000–5019 (reporting only),
control 9000–9009 (no storylines).

## Metrics engine and tools

Ingest, state and metrics are plain, deterministic code, not agents: numbers come from tools,
words from models.

```sh
uv run metrics summary m_1000              # match summary built from the tools
uv run python -m metrics.fit               # refit pass difficulty, xG, xT on calibration seeds
uv run python -m metrics.bench m_1000      # ingest/query cost during a 20x replay
uv run python -m eval.signal_check --mode tune   # signal check on tuning seeds (offline, reads ground truth)
```

- `metrics/store.py`: live match state, incremental ingest; queries never see past the latest ingested time.
- `metrics/tools.py`: typed tools (`get_window_stats`, `compare_windows`, `get_player_physical`,
  `get_sequence`, `get_moment_context`, `get_match_info`).
- `metrics/mcp_server.py`: the same tools over MCP, mounted in the API at `/mcp/`.
- Possession is **time-based possession** everywhere it appears.
- Pass difficulty, xG and xT are fitted on simulator output (calibration seeds), not on real football.
- The control index (0-100) is a documented heuristic (`metrics/models.py`).

Touches follow the event-data convention: one per on-ball action (pass, shot, tackle,
interception, clearance, ball recovery); receptions and carries are not counted separately.

### Do the hidden storylines move the numbers?

Each storyline type is checked against noise: the same window statistic on matches with no
storylines, scored with a robust z (median / MAD). Judged once on seeds never used for tuning
(storylines 2300–2399, no-storyline holdout 2400–2449):

| storyline | median z | detected above noise p95 | outcome |
|---|---|---|---|
| pressing_spell | 2.05 | 76 % | active |
| momentum_shift | 2.48 | 83 % | active |
| tactical_switch / long_ball | 2.52 | 83 % | active |
| tactical_switch / wide | 4.35 | 100 % | active |
| player_arc | 3.69 | 92 % | active, reported as *difficult* (visible too early in 2-minute slices) |
| fatigue_drop | 6.32 | 48 % | disabled |

On no-storyline holdout matches, requiring two signals above their own noise p95 flags
0.16–0.64 episodes per match for the active types. Full tables, protocol and the history of the
criterion: `docs/signal_check.md`. Performance: `docs/performance.md`.

## Agents (agents/)

Six agents in an Agent Framework graph workflow, one run per candidate moment:
**Detector → Analyst ⇄ Verifier → Narrator · Persona · Director**. Candidates come from code
(two metric signals above their noise level), so models are called only when something may
have happened. The Analyst reads numbers through the metrics MCP tools; the Verifier recomputes
every number it cites with the same tools (code) and checks the wording (agent); a rejection
goes back to the Analyst once. Narrator, Persona and Director fall back to templates on failure.

```sh
uv run python -m agents.run m_1000                 # MODEL_PROVIDER=fake: offline, free
uv run python -m agents.estimate m_1000 m_1001     # cost estimate of a Foundry run
MODEL_PROVIDER=foundry uv run --env-file .env python -m agents.run m_1000 --mode eval
uv run python -m eval.fit_detector                 # refit the candidate noise reference
```

The provider is an env switch (`MODEL_PROVIDER=fake | openai | foundry`, see `.env.example`).
Every run records tokens, latency and cost per call and stops at `RUN_BUDGET_EUR`; Foundry runs
also respect a cumulative cap (`FOUNDRY_TOTAL_CAP_EUR`) kept in a local spend ledger.

## Evaluation

Run once, on seeds never used for tuning: 20 eval matches (44 hidden storylines) and 10 control
matches with no storylines. Models: gpt-5.4-mini (Detector, Verifier) and gpt-5-mini (Analyst,
low reasoning effort) on Microsoft Foundry; 282 model calls, 0.39 EUR. Full report:
`docs/eval/report.html`, raw numbers `docs/eval/report.json`, and every recorded run in
`docs/eval/runs/`.

| Metric | Result |
|---|---|
| Storyline recall (approved explanation in the window ± 3 min, right team/player, right mechanism) | **52 %** (23 / 44) |
| Recall by type | tactical switch 6/8 · player arc 7/9 (rated *difficult* by the signal check) · momentum shift 6/12 · pressing spell 4/15 |
| Evidence validity (cited numbers recomputed by a second, independent code path) | **100 %** of the 267 items recomputed; 45 of 312 (14 %) could not be recomputed independently (see below) |
| Approved explanations with unsupported evidence | **0** of 81 |
| Precision (approved explanations that match a planted storyline) | 43 % |
| Precision@3 (the three moments per match the Director airs) | 48 % |
| Approved explanations per control match (no storylines planted) | 1.8 |
| Verifier rejections (claim sent back to the Analyst at least once) | 15 % |
| Latency p50 / p95: Detector · Analyst · Verifier (text) · candidate → approval | 1.3 / 2.0 s · 6.8 / 9.1 s · 1.1 / 1.5 s · 9.5 / 17.3 s |

Why 45 items are not independently checked: 23 cite xT added and 22 the control index. The
independent path recomputes from per-minute bins built from the match files, and these two
metrics need per-event model scores (xT) and possession-level detail (control index) that the
bins do not keep. They were still verified at approval time by the Verifier's recomputation
with the metrics tools; they are just not counted in the 100 %.

How to read precision: every approved explanation that does not match a planted storyline still
cites numbers that the independent recomputation confirms. They are **unplanted but
evidence-backed** patterns (54 of 81): real swings in the simulated match, such as a spell of
possession, that nobody scripted. They are not hallucinations; the metric counts them as misses
only because the evaluation can score against planted storylines alone. The same holds for the
control matches: the 1.8 explanations per match describe real fluctuations, with valid
evidence. What the system does not do is state numbers the data does not support.

Known limits: about a quarter of storylines produce no candidate from the code pre-filter;
pressing spells are often confused with momentum swings (both raise field tilt); and ordinary
fluctuations of the simulator are as strong and as persistent as planted ones, so the code
cannot separate them (checked on dev seeds).

## Front-end (web/)

Broadcast graphics follow `DESIGN.md` ("Verified on air"). Routes:

- `/broadcast?sample=hero_m_1000` — 16:9 broadcast frame over a recorded clip (`&t=<ms>` freezes it);
- `/graphics?sample=hero_m_1000` — the overlay layer alone, transparent, 1920×1080, for OBS or a vision mixer;
- `/design` — design reference: tokens, type, team colours over clashing kits, components.

The pitch canvas and every DOM overlay go through one projection (`web/src/lib/projection.ts`),
so tags and trails stay on the players with the pitch tilted. Fonts (Archivo, Inter) are
self-hosted under `web/public/fonts` with their SIL OFL licences. Review material:
`docs/design/`.

```sh
cd web && npm run dev                  # http://localhost:5173/broadcast?sample=hero_m_1000
npm test                               # projection and team-colour tests (node --test)
npm run capture -- audit "http://localhost:5173/broadcast?sample=hero_m_1000&t=4268900"
```

## Develop

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # fast suite
uv run pytest -m slow            # plausibility over 20 dev seeds
```

## Licence

MIT. See [`LICENSE`](LICENSE).
