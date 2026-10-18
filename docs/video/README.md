# Demo video: clips and voice-over

Under 2 minutes, following SPEC §11. Every clip is a screen recording of the real app replaying
**recorded agent runs** (real outputs of the pipeline on Microsoft Foundry), 1920×1080 at 30 fps
unless noted. Clips start after the page has loaded.

| # | Clip | Length | Shows |
|---|---|---|---|
| 01 | `01-landing.mp4` | 8 s | Landing: "Verified on air" |
| 02 | `02-broadcast-pass-card.mp4` | 15 s | Data graphics from code: pass trail, pass card with difficulty meter, player tags |
| 03 | `03-broadcast-speed-badge.mp4` | 8 s | Speed badge (33.2 km/h) following the player |
| 04 | `04-broadcast-shot-speed.mp4` | 8 s | Shot speed (112 km/h) with xG |
| 05 | `05-broadcast-template-to-verified.mp4` | 25 s | AI moment card: amber template with code numbers, then the verified text and the ✓ 3/3 seal (~11 s of real pipeline latency), caption |
| 06 | `06-split-analyst-en-casual-it.mp4` | 25 s | Split view: Analyst EN vs Casual IT with a favourite player; same numbers, same seal |
| 07 | `07-control-room-rejection.mp4` | 21 s (1600×1000) | Control room: agent graph, latencies, the Verifier rejecting a claim that credited two players already substituted off, the Analyst's corrected retry |
| 08 | `08-graphics-only-keyed.mp4` | 15 s | `/graphics` over a key colour: the overlay layer as a vision mixer would take it |
| 09 | `09-eval-report.mp4` | 20 s (1440×900) | Evaluation report, scrolling |
| 10 | `10-architecture.mp4` | 9 s | Architecture on Azure |
| 11 | `11-second-screen.mp4` | 8 s (390×844) | Second screen in Italian |

Suggested cut: 01 (0:00) → 02 (0:06) → 05 (0:16) → 03 / 04 as inserts → 06 (0:42) → 07 (1:06) →
08 (1:28) → 09 (1:34) → 10 (1:48) → 01 or 11 to close (1:55).

## Voice-over (English, about 260 words, ~1:55 at a calm pace)

**[0:00, landing]**
A scoreline tells you who is winning. It doesn't tell you why. Ground Truth Football is a
team of AI agents that watches a match and explains it live, and every number they cite is
recomputed by code before it goes on air.

**[0:06, pass card, speed, shot]**
Data graphics come straight from code: pass difficulty, top speed, shot speed and expected
goals, the instant they happen.

**[0:16, template to verified card]**
When something changes, code flags it first. The Director puts a template on air, in amber,
with numbers computed by code. Behind it, six agents built on Microsoft Agent Framework go to
work. An Analyst explains what changed using metrics tools over MCP. A Verifier recomputes
every number and checks the wording. Only then does the verified card replace the template,
with its seal.

**[0:42, split view]**
The same facts, told for different viewers. An analyst in English. A casual fan in Italian,
following a favourite player. The numbers and the seal never change; only the telling does.

**[1:06, control room]**
This is the control room. Here the Analyst credited two players who had already been
substituted. The Verifier rejected the claim with its reason; the Analyst tried again, and
only the corrected version went on air.

**[1:28, graphics only]**
The graphics layer runs on its own, ready for a vision mixer.

**[1:34, eval report]**
We measured it on matches with hidden storylines the agents never see: half of the planted
stories found, and no approved explanation with a number the data does not support.

**[1:48, architecture]**
It runs on Azure: Container Apps, Foundry models, PostgreSQL, Blob Storage and Application
Insights.

**[1:55, close]**
Ground Truth Football. Verified on air.

Notes on accuracy (for the edit):
- "half of the planted stories found": recall 52 % (23 of 44) on 20 unseen evaluation matches.
- "no approved explanation with a number the data does not support": 0 unsupported of 81
  approved; 267 evidence items recomputed independently, all confirmed; 45 items (xT, control
  index) are checked only by the Verifier's own recomputation.
- The rejection in clip 07 comes from the official evaluation run of match m_5016 (pipeline at
  commit df03ba1); see the reviewer note shown in the clip.
- All clubs, players and data are synthetic.
