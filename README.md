# Regista

<img src="docs/brand/regista-wordmark.png" alt="Regista" width="260">

**Reads the game. Directs the broadcast.** AI match graphics and tactical explanations,
generated live, and checked before they go on air: a multi-agent system that watches a football
match, explains what changed and why in broadcast graphics for different viewers, and checks
every number it cites against a code recomputation before it goes on screen. Built on Microsoft
Agent Framework and Microsoft Foundry, deployed on Azure, and measured against hidden
storylines the agents never see.

In Italian, *regista* is both the playmaker who reads the game and the TV director who decides
what goes on air. (Until 18 October 2026 the project was called *Ground Truth Football*.)

All data is synthetic; all clubs, players, venues and competitions are fictional.

## The problem

On TV, graphics like "shot at 112 km/h" and lines like "they've been pressing high for ten
minutes" are prepared by a team of analysts and designers. That is expensive, so it happens only
for big matches and in few languages. AI could do it for every match and every viewer, but on
live TV one invented number is a disaster: the hard part is trust. Regista generates the graphics
and explanations live, recomputes every number an agent cites before it goes on screen, and
measures how often it finds what really happened.

## Live demo

**https://gtf-app.delightfulbush-9c2f92ce.italynorth.azurecontainerapps.io**

No login, account or key is needed: open the link in any browser. Everything below works on
recorded agent runs except the live session (last row), so it costs nothing to explore.

| Start here | What you see |
|---|---|
| `/tour` | **Guided tour, about 2 minutes**: the best moments of the recorded runs in sequence, each with a caption saying whether code or an AI agent made it |
| `/` | Landing: what it does, why it can be trusted, results, and links to every screen |
| `/broadcast` | Broadcast player on a **recorded agent run**: clickable timeline of key moments, "next key moment" (N), auto-skip of quiet play, moment replay with telestration, insights feed, and the evidence behind every AI card (press the ✓ seal) |
| `/split` | The same moment for two viewers: Analyst in English, casual fan in Italian with a favourite player |
| `/control` (from the landing) | Control room: the agent graph at work, with a real Verifier rejection and its reason |
| `/graphics` | The overlay layer alone, transparent 1920×1080, for OBS or a vision mixer |
| `/eval` | Evaluation report |
| `/broadcast?live=m_1000&speed=4` | Live session: the agents run for real on Foundry (capped per day) |

Recorded agent runs are real, saved outputs of the pipeline, replayed with zero model calls.
Live sessions call the models and stop when the daily cap is reached.

## How it works

```
simulator ──► live store + metrics engine (code) ──► MCP server: 6 typed tools
                       │
                 candidates (code: 2 signals above their noise level)
                       │
   Agent Framework workflow:  Detector → Analyst ⇄ Verifier → Narrator · Persona ×9 · Director
                       │                    (code recomputes every number, a model checks the
                       │                     wording; one retry with the reason)
                       ▼
     overlay timeline: tier 0 data graphics at once, tier 1 template → verified text
                       ▼
     WebSocket ──► broadcast front-end (React), /graphics for OBS
```

- **Numbers from tools, words from models.** Ingest, state and metrics are deterministic code;
  agents read numbers only through the metrics tools (MCP). Every number in a claim must come
  from the evidence, which the Verifier recomputes with the same tools before approving.
- **Six agents with distinct roles**: Detector (is this worth explaining?), Analyst (why it
  matters, with evidence), Verifier (hybrid: code + model), Narrator (caption), Persona (nine
  viewer profiles: analyst, casual, player focus × English, Italian, Spanish), Director (when and
  how long on air). Failures fall back to templates, so the broadcast never stops.
- **Captions and persona lines are checked by code** against the verified claim: a line that
  adds a number or a player the claim does not contain is replaced by a template.
- **Ground truth is isolated by construction**: it is written to a separate directory, never
  mounted, uploaded or copied into the image; tests scan the runtime code for any reference.

## Run locally

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node 22. Agents run offline with the
scripted fake client by default (`MODEL_PROVIDER=fake`); Foundry needs `az login` and `.env`.

```sh
cp .env.example .env            # model settings for MODEL_PROVIDER=foundry
# The matches of the recorded runs in data/recorded (tracking is not committed; ~6 s each):
for s in 1000 1003 1009 5016; do uv run sim generate --seed $s; done
docker compose up -d --build    # PostgreSQL + API on :8000
curl localhost:8000/health      # {"status":"ok","db":"ok"}

cd web && npm install && npm run dev   # front-end on :5173, proxies the API
```

Then open http://localhost:5173/tour. The simulator is deterministic, so the generated matches
are the ones the recorded runs were made on.

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
uv run --env-file .env python -m agents.smoke       # one call per Foundry deployment (auth check)
```

System prompts, one per agent, are in [`agents/prompts/`](agents/prompts) with a table of agent,
model and output schema.

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
| Precision (approved explanations that match a planted storyline, in the 20 matches with storylines) | 43 % (27 / 63; the other 18 of the 81 approved are in the control matches) |
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
cites numbers that the independent recomputation confirms (wherever it can check them; see above). They are **unplanted but
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

Broadcast graphics follow `DESIGN.md` ("Verified on air"). Every replay is a **Recorded agent
run**: a real, saved output of the pipeline (`data/recorded/`), replayed with zero model calls;
live sessions are labelled **Live**. Routes:

- `/tour` — guided tour (≈ 2 min; `?step=<n>` starts at a step);
- `/` — landing; `/broadcast?run=<id>&persona=analyst_en` — broadcast player with the full
  package (scorebug, player tags, pass card, speed and shot badges, stat compare, momentum
  ribbon, AI moment card: amber template first, then the verified text with its seal; caption),
  plus the match timeline, next key moment (N), auto-skip of quiet play, moment replay (Space
  continues) and the insights feed; `&clean=1` shows the bare 16:9 programme;
  `/broadcast?live=m_1000` — live session over the API WebSocket (agents run, daily cap);
- `/split?run=<id>&left=analyst_en&right=casual_it` — same moment for two viewers;
- `/control?run=<id>` — control room: the agent graph, verdicts, Verifier rejections with the
  reason, latency per stage;
- `/graphics?run=<id>` — overlay layer alone, transparent 1920×1080, for OBS or a vision mixer;
- `/eval` — evaluation report; `/second` — second screen (390 px); `/recap` — full-time recap;
- `/design` — design reference.

Streams: `/ws/recorded/{run_id}` and `/ws/live/{match_id}` send the same messages (`frame`,
`event`, `overlay`, `pipeline`), so every screen works on both. On a recorded run the client can
change the playback rate (`{"type": "pace", "speed": 0..100}`, 0 holds the stream): that is how
the player pauses, fast-forwards quiet play and holds a moment replay; seeking reconnects with
`from_ms`, and the earlier events arrive first in one `events` message. `/api/runs/{id}/timeline` gives the timeline markers (goals, shots, red cards, Verifier
rejections) and the telestration of each verified moment, computed by code from the public
match events (`metrics/telestration.py`): where the team wins the ball back, how wide it plays,
its longest passes, a player's progressive passes, or its final-third actions.

The pitch canvas and every DOM overlay go through one projection (`web/src/lib/projection.ts`),
so tags and trails stay on the players with the pitch tilted. Fonts (Barlow Condensed, Barlow,
Newsreader) are self-hosted under `web/public/fonts` with their SIL OFL licences. Review
material: `docs/design/`.

```sh
cd web && npm run dev                  # http://localhost:5173/tour
npm test                               # projection and team-colour tests (node --test)
./scripts/audit.sh                     # layout audit: replays, telestration, evidence, insights at 1920, 1440, 390 px
```

## Azure deployment

`infra/deploy.sh` (Azure CLI) creates, in Italy North:

| Service | Use |
|---|---|
| Azure Container Apps | one container: FastAPI backend + built front-end (0.25 vCPU / 0.5 GiB, one replica) |
| Microsoft Foundry | `gtf-fast` = gpt-5.4-mini (Detector, Verifier, Narrator, Persona, Director), `gtf-reasoning` = gpt-5-mini (Analyst, low reasoning effort) |
| Azure Database for PostgreSQL Flexible | runs and moments (Burstable B1ms) |
| Azure Blob Storage | demo matches and recorded runs, downloaded at startup (read-only, allowlist of public files) |
| Application Insights | OpenTelemetry traces from Agent Framework |
| GitHub Actions + GHCR | CI; the image is pushed only after CI passes |

The container app has a managed identity with two roles: *Storage Blob Data Reader* on the
storage account and *Cognitive Services User* on the Foundry resource (model calls for live
sessions; it is the narrowest built-in role that covers Foundry project inference, and it also
allows reading account keys). No keys are stored in the app or the repo; the database password
is a Container App secret.

Model choice: GPT-6 / GPT-5.6 quota is not available for this subscription, so the agents use
gpt-5.4-mini and gpt-5-mini, which have default quota. Model spend for the whole project
(prompt tuning, evaluation, recorded runs) was about 1.76 EUR, tracked per call; live sessions
are capped at 150 model calls per day in production (`LIVE_DAILY_MODEL_CALL_CAP`, set by
`infra/deploy.sh`; the local default is 2000). `infra/post_judging.sh` removes PostgreSQL and lets the
app scale to zero after the judging period.

## Repository structure

| Path | What |
|---|---|
| `sim/` | Match simulator (events + 10 Hz tracking, hidden storylines) and the paced replay stream |
| `metrics/` | Deterministic metrics engine: live store, pass difficulty, xG, xT, control index, telestration; the typed tools and their MCP server |
| `agents/` | Candidate finder, Agent Framework workflow, model providers and cost meter, overlay timeline, live sessions; `prompts/` holds one system prompt per agent |
| `api/` | FastAPI app: REST, recorded and live WebSockets, MCP mount, PostgreSQL, Blob data sync, telemetry; serves the built front-end |
| `web/` | React + TypeScript front-end (Vite): broadcast package, player, tour, split view, control room, pages; `scripts/` captures screenshots, video and layout audits |
| `eval/` | Evaluation harness and scorer, signal check, detector noise fit |
| `infra/` | Azure deployment scripts (see [`infra/README.md`](infra/README.md)) |
| `tests/` | pytest suite: simulator, metrics, agents with the fake client, API, ground-truth isolation, data sync |
| `data/` | `recorded/`: the recorded agent runs the demo replays; `samples/`: one match without tracking. Git-ignored: `generated/` (simulator output), `ground_truth/` (hidden storylines), `runs/` (local run JSONs and spend ledger) |
| `docs/` | Evaluation report, signal check, performance, demo video, design review, brand (see [`docs/README.md`](docs/README.md)) |
| `.github/workflows/` | `ci.yml` (lint, types, tests, front-end build), `image.yml` (container image to GHCR after CI passes on `main`) |
| `SPEC.md`, `DESIGN.md`, `STATUS.md` | Technical spec, design direction, progress and decisions |

## Develop

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # fast suite
uv run pytest -m slow            # plausibility over 20 dev seeds
cd web && npm run lint && npm test && npm run build
```

## Documents

[`SPEC.md`](SPEC.md) (technical spec) · [`DESIGN.md`](DESIGN.md) (design direction) ·
[`STATUS.md`](STATUS.md) (progress, decisions, spend) · [`docs/`](docs) (signal check, evaluation,
design review, demo video clips and voice-over).

## Licence

MIT. See [`LICENSE`](LICENSE).
