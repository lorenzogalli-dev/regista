# Regista — Technical Spec

> The project was called *Ground Truth Football* until 2026-10-18; the name changed, the spec did not.

> Microsoft × Premier League Hackathon (submission deadline: 27 Oct 2026, 23:59 PT)
> Target category: **Best Multi-Agent System** (+ Grand Prize eligibility)

## 1. One-line pitch

A multi-agent system on Microsoft Foundry that turns a live stream of synthetic football events and tracking into explainable, personalised on-screen intelligence — and **proves how often its explanations are right**, because the synthetic matches carry a hidden ground-truth storyline the agents never see.

## 2. Scope

### In scope
- Synthetic match simulator (events + 10 Hz tracking) with hidden, seeded storylines.
- Deterministic metrics engine (all numbers come from code, never from an LLM).
- Multi-agent pipeline: detect → explain → verify → narrate → personalise → direct (overlay).
- Web front-end and broadcast graphics package, as specified in `DESIGN.md`.
- Evaluation harness that scores explanations against the hidden storylines.
- Deployment on Azure (Container Apps) with Foundry-hosted models.
- Judge access: the deployment stays up, free and unrestricted, until the end of the Judging Period (10 Nov 2026). Recorded agent runs work with zero model calls; live mode is capped (§9.1).

### Out of scope (unless time remains)
- Real match footage of any kind. **All data is synthetic; all clubs and players are fictional.**
- No computer vision or video processing of any kind.
- No code from any pre-existing project. Everything in the repo is written after 29 Sep 2026.

## 3. Data model

### 3.1 Coordinate system
- Pitch 105 × 68 m, origin bottom-left, x along the length.
- Stored in **absolute** coordinates. A helper converts to "attacking left→right" per team for metrics.
- Time: `t_ms` since kickoff of the match (continuous across halves; `period` tells the half).

### 3.2 Match metadata (`match.json`)
```json
{
  "match_id": "m_0001",
  "seed": 42,
  "competition": "Synthetic League",
  "venue": "Fictional Park",
  "home": {"team_id": "t_hrb", "name": "Harbour Rovers", "short": "HRB",
           "colors": ["#0B3D91", "#FFFFFF"], "formation": "4-3-3",
           "style": {"press_intensity": 0.7, "directness": 0.4, "width": 0.6}},
  "away": { "...": "same shape" },
  "players": [
    {"player_id": "p_hrb_07", "team_id": "t_hrb", "name": "Teo Marlow", "shirt": 7,
     "position": "RW", "attrs": {"top_speed_ms": 9.6, "accel": 0.8, "passing": 0.7,
     "finishing": 0.75, "stamina": 0.6}}
  ]
}
```

### 3.3 Event (`events.jsonl`, one per line, time-ordered)
| field | type | notes |
|---|---|---|
| `event_id` | str | unique, monotonic |
| `match_id` | str | |
| `t_ms` | int | |
| `period` | int | 1, 2 |
| `type` | enum | `kickoff, pass, carry, shot, save, goal, tackle, interception, clearance, pressure, foul, card, sub, ball_recovery, possession_change, period_start, period_end` (`duel` cut; `foul`, `card`, `sub` kept as `momentum_shift` triggers) |
| `team_id`, `player_id` | str/null | actor |
| `x`, `y` | float | start location (m) |
| `end_x`, `end_y` | float/null | for pass/carry/shot |
| `outcome` | enum/null | `complete, incomplete, on_target, off_target, blocked, won, lost, ...` |
| `recipient_id` | str/null | pass receiver |
| `possession_id` | int | increments on every possession change |
| `qualifiers` | object | type-specific: `body_part`, `height`, `under_pressure`, `ball_speed_ms`, `xg`... |

### 3.4 Tracking frame (`tracking.jsonl`, 10 Hz)
```json
{"t_ms": 123400, "ball": {"x": 52.1, "y": 30.2, "z": 0.1, "speed_ms": 14.2},
 "players": [{"player_id": "p_hrb_07", "x": 70.3, "y": 55.0, "speed_ms": 7.9}]}
```

### 3.5 Hidden ground truth (`storylines.json`) — **never readable by agents**
```json
{
  "storyline_id": "s_03",
  "type": "pressing_spell",
  "start_ms": 3600000, "end_ms": 4200000,
  "team_id": "t_hrb", "actors": ["p_hrb_08", "p_hrb_10"],
  "mechanism": {"press_intensity": "0.7 -> 0.95"},
  "expected_signals": [
    {"metric": "ppda", "team": "t_hrb", "direction": "down"},
    {"metric": "opp_pass_completion", "team": "t_awy", "direction": "down"},
    {"metric": "field_tilt", "team": "t_hrb", "direction": "up"}
  ],
  "canonical_explanation": "Harbour Rovers raised their press after the hour; the away side's build-up broke down and play tilted into their half."
}
```
Storyline types (aim for 5):
- `pressing_spell` — press intensity raised for a time window.
- `fatigue_drop` — one player's top speed and sprint count decay; opponents target their flank.
- `momentum_shift` — after an event (goal, red card, sub), possession and field tilt flip.
- `tactical_switch` — width/directness change (e.g. switch to long balls).
- `player_arc` — a player has an outlier game (e.g. many progressive passes, a record sprint).

Status (2026-10-18, official signal check in `docs/signal_check.md`): active `pressing_spell`, `momentum_shift`, `tactical_switch` (`long_ball`, `wide`); `player_arc` active as a "difficult" storyline (reported separately in the eval); `fatigue_drop` implemented but disabled.

Storyline scheduling:
- **2–3 storylines per match**, drawn from the seed, with **non-overlapping** windows.
- `momentum_shift` does not wait for a random event: the simulator **forces the trigger event** (red card, substitution or goal) at a scheduled minute, then applies the modifiers.
- **Control seeds** are generated with **zero storylines**. They measure how often the system "finds" a story in pure noise (§7).
- `storylines.json` is written to `GROUND_TRUTH_DIR`, a directory separate from `events`/`tracking`, never mounted into the API/agent runtime, never copied into images, never exposed by any tool, MCP server or endpoint. A test enforces this.

## 4. Simulator

- **Deterministic** from `seed`. Same seed → byte-identical output.
- Events and tracking are generated **in the same simulation loop** (pressure on the ball carrier is read from the current tracking state, not reconstructed afterwards).
- If the schedule is at risk, tracking fidelity is cut first (formation anchors + ball attraction + noise), never event/storyline logic.
- Possession engine: a zone-based state machine (pitch split into e.g. 6×4 zones). At each step the ball carrier picks an action (pass/carry/shot) with probabilities shaped by zone, team style and player attributes; outcome probabilities shaped by pressure (nearest defender distance from tracking) and skill.
- Tracking: each player has a formation anchor that shifts with ball position and team phase (in/out of possession), plus attraction to the ball for nearby players and noise. Speed and acceleration are capped by attributes × current fatigue. Ball moves along pass/shot trajectories with realistic speeds (passes 8–25 m/s, shots 15–35 m/s).
- Fatigue: stamina-dependent decay of top speed over the match.
- Storylines are **parameter modifiers over time windows** (e.g. raise `press_intensity` from minute 60 to 70). The simulator writes `storylines.json` with the realised windows.
- Plausibility targets per 90 min (sanity tests): ~900–1100 passes total, 20–30 shots, 1–4 goals on average across seeds, pass completion 75–88 %, top player speeds 8.5–10 m/s.
- **Replay server**: streams `events` + `tracking` in real time with a speed factor (1×, 4×, 20×) over WebSocket or SSE.

## 5. Metrics engine (deterministic, no LLM)

Rolling windows (5 and 15 min) plus match totals:
- Possession %, field tilt (share of final-third ball actions: passes, carries, shots), PPDA, pass completion.
- **Pass card**: length, progression, and a **pass difficulty score 0–1** = logistic over (length, receiver pressure, number of defenders near the passing lane, under_pressure flag). Documented formula, unit-tested.
- **Speed**: ball speed on shots and passes; player top speed, sprint count (> 7 m/s), high-intensity distance (> 5.5 m/s), distance covered.
- xG (simple logistic on distance + angle + body part), **coefficients fitted on synthetic shots**. xT on a 12×8 grid, **computed by value iteration over simulated matches** (no third-party xT table). Both are documented as "calibrated on the simulator, not on real football".
- **Rhythm / control vs chaos index**: mean possession length, turnovers per minute, event-rate variance, share of possessions ending in the opponent half. Combine into a documented 0–100 "control" index.
- **Threshold triggers** for overlays: player speed > 9 m/s, shot speed > 30 m/s, pass difficulty > 0.8, etc.

API: `get_window_stats(team, start_ms, end_ms)`, `compare_windows(...)`, `get_player_physical(player_id, ...)`, `get_sequence(possession_id)`, `get_moment_context(t_ms)`. These are the **tools** the agents call.

The tools are exposed through an **MCP server** (Python `mcp` package) and consumed by the Analyst and Verifier through Agent Framework's MCP support. The MCP server has no access to `GROUND_TRUTH_DIR`; isolation is structural, and tested.

## 6. Agent architecture

Principle: **numbers from tools, words from models.** Every claim an agent makes must reference metric values returned by a tool call; a verifier rejects unsupported claims.

```
[Replay stream] → Ingest/State (code) → Metrics engine (code)
                                   │
                        Moment Detector agent ──► candidate moments
                                   │
                         Analyst agent (tools) ──► Explanation {claim, evidence[]}
                                   │
                         Verifier agent ──(reject → retry once)──┐
                                   │ approved                    │
                 ┌─────────────────┼──────────────────┐         │
          Narrator agent     Persona agent      Director agent ◄┘
       (captions, recap)  (per profile/lang)  (overlay timeline JSON)
                                   │
                          WebSocket → front-end
```

| Agent | Role | Inputs | Output |
|---|---|---|---|
| **Moment Detector** | Ranks rule-based candidates (trigger fired, xT swing, metric change-point) and labels them | candidate list + context | `Moment {moment_id, t_ms, kind, actors, salience}` |
| **Analyst** | Explains *why* it matters, using tools | moment + tools | `Explanation {moment_id, claim, mechanism_tag, evidence:[{metric, team/player, before, after}], confidence}` |
| **Verifier** (hybrid) | **Code** recomputes every evidence item (before/after within tolerance); the **agent** checks that the claim text is consistent with the evidence (direction, subject, no numbers absent from evidence). Either failing rejects. | explanation | `approved / rejected + reason` |
| **Narrator** | Live one-liners + half-time and full-time recaps | approved explanations + match state | captions, recap text |
| **Persona** | Rewrites the same approved facts per viewer profile and language | facts + `PersonaProfile` | persona-specific text and overlay selection |
| **Director** | Decides what goes on screen, when, for how long; rate-limits and prioritises | all of the above | overlay timeline (schema 6.2) |

Ingest, state and metrics are plain code, not agents — say so in the README; it is a design choice, not a gap.

Models: two Foundry deployments from env — `FOUNDRY_MODEL_REASONING` = `gtf-reasoning` (**gpt-5-mini**, Global Standard, low reasoning effort; Analyst only) and `FOUNDRY_MODEL_FAST` = `gtf-fast` (**gpt-5.4-mini**, Data Zone Standard EU; Detector, Verifier, Narrator, Persona, Director). Why these: GPT-6 and GPT-5.6 quota is not available for this subscription (0 TPM in every region, checked 2026-10-18), while these two have default quota; the choice is final, not a fallback. The provider is chosen by env (`MODEL_PROVIDER=fake | openai | foundry`); development and tests use the scripted fake client (GitHub Models was retired on 2026-07-30). Foundry is used only for prompt tuning on a few dev matches, the evaluation and the recorded agent runs, each after a cost estimate (`agents.estimate`) and within a per-run budget cap (`RUN_BUDGET_EUR`). Total Azure spend for the hackathon is capped at 10 EUR, of which at most 8 EUR on Foundry models (cumulative cap enforced in code).

Candidate moments are found by code (`agents/candidates.py`): every minute of match time, each storyline type's signals over the recent window are scored against noise (robust z, noise fitted on no-storyline seeds) and a candidate needs two signals above their noise p95 (a single-signal type needs its p99). Only candidates reach the Detector agent, so model calls scale with candidates, not with match time.

### 6.0 Two overlay tiers
- **Tier 0 — data graphics, code only, immediate:** speed badge, pass card, shot speed, player tag, stat compare, momentum/control ribbon. Emitted directly from metrics threshold triggers; no agent in the path.
- **Tier 1 — AI insight graphics, agents:** moment cards, captions, recaps. They arrive seconds after the moment; that latency is measured and reported, not hidden.
- For tier 1 the Director emits a **deterministic template first**, then replaces it with model text when (and if) it arrives. The overlay stream never stops.

### 6.0.1 Personas
- Precomputed fixed set: `analyst`, `casual`, `player_focus` × languages **en / it / es**.
- A custom favourite player is generated on demand and cached. `club_focus` is a filter over existing output, not an extra agent call.

### 6.1 Shared state and resilience
- Shared match state store (Azure Database for PostgreSQL, or in-memory + Postgres snapshot for the demo).
- Every agent call has a timeout. On failure or timeout: Narrator and Director fall back to **deterministic templates** so the overlay stream never stops; the failure is logged and visible in a debug panel.
- Verifier rejection → one retry with the rejection reason; second rejection → moment dropped and logged.
- Tracing to Application Insights (OpenTelemetry), one trace per moment across all agents.

### 6.2 Overlay schema
```json
{
  "overlay_id": "o_0412",
  "source_moment_id": "mo_0098",
  "show_at_ms": 3712400, "duration_ms": 6000, "priority": 2,
  "kind": "player_tag | speed_badge | pass_card | shot_speed | moment_card | stat_compare | momentum_bar | caption",
  "anchor": {"type": "player | pitch | screen", "player_id": "p_hrb_07", "x": null, "y": null, "region": null},
  "payload": {"title": "", "value": "", "unit": "", "text": ""},
  "persona_id": "casual_it", "lang": "it"
}
```

### 6.3 Persona profile
```json
{"persona_id": "casual_it", "mode": "analyst | casual | player_focus | club_focus",
 "lang": "en", "favorite_team_id": "t_hrb", "favorite_player_id": "p_hrb_07",
 "focus_metric": null, "verbosity": "low | medium | high"}
```

## 7. Evaluation harness

Runs the 20 eval seeds (5000–5019) and the 10 control seeds (9000–9009) offline, as fast as possible (not paced), once. It reports:
- **Storyline recall** — share of hidden storylines for which at least one approved explanation falls in the window (± 3 min), names the right team or actors, and has a `mechanism_tag` matching the storyline type.
- **Explanation precision** — share of approved explanations that match a storyline. (Evidence correctness is reported separately below, so precision is not trivially 100 %.)
- **Evidence validity** — share of approved evidence items that pass recomputation by a code path **independent of the Verifier's**.
- **False alarms on control seeds** — approved storyline-type explanations per match on seeds with zero storylines.
- **Hallucination rate** — share of Analyst outputs rejected by the Verifier, plus share of approved outputs failing the independent recomputation.
- **Categories of approved explanations** — storyline hit; unplanted but evidence-backed (no storyline, every independently checkable evidence item confirmed: a real pattern in the data, not an error); unsupported (an evidence item fails, or none can be checked).
- **Precision@3** — precision on the three highest-salience approved moments per match (what the Director airs).
- **Recall by type**, with types rated "difficult" by the signal check flagged.
- **Latency** — p50/p95 from event to overlay emission.
- Output: `docs/eval/report.json`, `docs/eval/report.html` and every run JSON (`eval/run_eval.py`; dev runs go to `eval/out/dev/`). These numbers go in the README and in the demo video.

Report honest numbers. Do not tune on the evaluation seeds (keep separate dev and eval seed sets).

## 8. Front-end

**Replaced by `DESIGN.md`**, which is binding for the whole front-end, including the broadcast ("TV") graphics package, the graphics-only `/graphics` route (transparent 1920×1080), the screens and the quality bar.

Delivery D5 is split:
- **D5a — design system + hero frame**, right after D2, on a generated sample match. Approved by screenshots before anything else is built. The `motion` dependency is proposed in the D5a plan.
- **D5b — full graphics package and all screens**, after D3/D4.

Every replay is a **real, saved output of the agent pipeline**, labelled **"Recorded agent run"**; live sessions are labelled **"Live"**.

## 9. Azure / Microsoft stack

- **Microsoft Foundry**: model deployments, agents, tracing/evaluation where useful.
- **Microsoft Agent Framework** (Python) for the agents and the orchestration workflow.
- **Azure Container Apps**: a single container app serving the backend (FastAPI) and the built front-end.
- **Azure Database for PostgreSQL** (flexible server, **smallest Burstable tier**) for shared state and run history.
- **Application Insights** for traces.
- **MCP** server for the metrics tools (§5).
- Cut: Azure Event Hubs, Translator comparison.
- GitHub Actions for CI (lint, tests, sim determinism test).

### 9.1 Cost controls
- **Recorded agent runs** are real pipeline outputs saved to the database and replayed with zero model calls.
- **Live mode** has a **daily cap on model calls** (`LIVE_DAILY_MODEL_CALL_CAP`). When the cap is reached, live sessions are refused with a clear message in the UI and recorded runs stay available. The remaining quota is shown on the landing page.
- Azure budget alerts are configured manually by the owner, outside the repo.

## 10. Repo layout
```
/sim            simulator + replay server
/metrics        deterministic metrics engine + tools API
/agents         agent definitions, prompts, workflow
/api            FastAPI app (WebSocket stream, REST)
/web            front-end
/eval           harness + reports
/data/samples   a few generated matches (small)
/infra          Azure deployment (Bicep or az CLI script) + README
/docs           architecture diagram, demo script
SPEC.md  DESIGN.md  README.md  STATUS.md  LICENSE (MIT)
```

## 11. Demo video (< 2 min)
1. 0:00–0:15 — The problem: the scoreline doesn't tell the story.
2. 0:15–0:45 — Live pitch with overlays: speed badge, pass difficulty card, moment card with explanation.
3. 0:45–1:10 — Split screen: analyst vs. casual fan in Italian, favourite-player focus.
4. 1:10–1:30 — Agent trace: claim → evidence → verifier verdict; a rejected hallucination and the fallback.
5. 1:30–1:50 — Eval report: storyline recall, hallucination rate, latency. Architecture on Azure.
6. 1:50–2:00 — Close.

No third-party trademarks, real clubs, real players or copyrighted music.

## 12. Plan

| Date | Delivery |
|---|---|
| 17–19 Oct | Register (closes 20 Oct, 12:00 PT). D0 skeleton, D1 simulator + storylines, D2 metrics engine |
| 20 Oct | D5a design system + hero frame (screenshot approval) |
| 20–21 Oct | D3 agents + orchestration |
| 22–23 Oct | D4 eval harness, prompt iteration on dev seeds |
| 24–25 Oct | D5b full graphics package + screens + personas |
| 26 Oct | D6 Azure deploy, README, video |
| 27 Oct | Buffer, submit |

## 13. Risks
- **Agent latency** too high for "live": tier-0 graphics never wait for agents (§6.0); batch per moment, use a smaller model for Narrator/Persona, templates as fallback, run the demo at 1× on a short excerpt.
- **Simulator realism** eats time: cap at the plausibility targets in §4; realism beyond that does not win points.
- **Over-scoping**: nothing beyond D6. Spare time goes into eval quality and the demo video.
- **SDK churn**: Agent Framework / Foundry APIs change quickly — verify against current docs before coding.
