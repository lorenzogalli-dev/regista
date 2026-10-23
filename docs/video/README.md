# Demo video: clips and voice-over

**Final video: [`regista-demo.mp4`](regista-demo.mp4)** (1:39, 1920×1080, H.264 + AAC) with English
subtitles burned in and as [`regista-demo.srt`](regista-demo.srt). It is built from the clips below,
three title cards in the site's style and a voice-over by **Azure AI Speech** (neural voice
`en-GB-RyanNeural`, on the project's Foundry resource with Entra ID, no keys; ~3,000 characters,
about 0.04 EUR). No music.

```sh
python3 docs/video/build/make_video.py --voice azure   # or --voice say: free local draft voice
```

`build/make_video.py` synthesises every voice-over line separately, so each subtitle and cut follows
the line's exact length (measured: subtitles within 0.03 s of the speech), and the build stops if
any pause between two lines exceeds 1.5 s or the video reaches 1:55; the readable elements (the
amber and the verified AI card, the Verifier's rejection, the stack tiles) get a short slow zoom; `build/cards.html` holds
the title cards and overlays, recorded with `web/scripts/capture.mjs`. Intermediate files go to
`build/out/` (git-ignored).

Under 2 minutes, following SPEC §11. The **guided tour** (`/tour`) is the backbone: clips 02–07
are cut from one real-time recording of it (`docs/design/regista/guided-tour.mp4`, 124 s,
1920×1080). Every scene is the real app replaying **recorded agent runs** (real outputs of the
pipeline on Microsoft Foundry) with zero model calls. Clips are 1920×1080 at 30 fps unless
noted; tour clips start on the step change, so trim about 1 s of loading at their head.

| # | Clip | Length | Shows |
|---|---|---|---|
| 01 | `01-landing.mp4` | 12 s | Landing hero: "Reads the game. Directs the broadcast.", the real broadcast playing beside it, "Take the 2-minute tour" |
| 02 | `02-tour-intro.mp4` | 6 s | Tour title card |
| 03 | `03-tour-data-graphics.mp4` | 22 s | **Code**: pass card with difficulty meter, top speed badge (33.4 km/h), shot speed (112.4 km/h) with xG |
| 04 | `04-tour-ai-insight-replay.mp4` | 39 s | Code spots a change → amber template on air → verified AI card with the ✓ 4/4 seal → **moment replay**: the frame holds, the final third is shaded from the match data (46 vs 23 final-third actions) → the evidence panel: every cited number, before and after |
| 05 | `05-tour-split.mp4` | 17 s | Same moment for an analyst in English and a casual fan in Italian following a favourite player |
| 06 | `06-tour-control-room.mp4` | 24 s | Control room: moments travel through the agent graph; the Verifier rejects a claim that credited two players already substituted off; the corrected claim goes on air |
| 07 | `07-tour-results.mp4` | 16 s | Results: 52 %, 0 / 81, ≈ €1.76 |
| 08 | `08-player-timeline-skip.mp4` | 14 s | Broadcast player: timeline with AI (cyan) and data (green) markers, "Skipping quiet play ×8", insights feed |
| 09 | `09-graphics-only-keyed.mp4` | 15 s | `/graphics` over a key colour: the overlay layer as a vision mixer would take it |
| 10 | `10-eval-report.mp4` | 20 s (1440×900) | Evaluation report, scrolling (nav hidden for the recording: `STYLE='.site-nav{display:none!important}'`) |
| 11 | `11-landing-scroll.mp4` | 28 s (1440×900) | Landing scrolled top to bottom: problem, what it does, trust schema, results, explore, under the hood (pipeline and Microsoft technologies) |
| 12 | `12-second-screen.mp4` | 8 s (390×844) | Second screen |

Suggested cut (≈ 1:55): 01 (0:00–0:06) → 03 (0:06–0:20, trimmed) → 04 (0:20–0:56) → 05
(0:56–1:08) → 06 (1:08–1:28) → 09 as an insert (1:28–1:32) → 11, under-the-hood part
(1:32–1:42) → 07 (1:42–1:55). Use 02, 08, 10, 12 as alternatives.

## Voice-over (final, 253 words)

**[0:00.0, title card; only the first sentence is subtitled, the card shows the rest]**
This is Regista. Live match graphics and tactical analysis take a team of analysts, so most matches never get them. Regista generates them live, and checks every number before it goes on air.

**[0:11.6, tour: data graphics]**
Some graphics need no AI at all. Pass difficulty, top speed, shot speed and expected goals are computed by code, the instant they happen.

**[0:21.5, tour: template, verified card, moment replay]**
When the game shifts, code notices first, and a template goes on air at once. Behind it, six agents on Microsoft Agent Framework and Foundry go to work, reading numbers only through metrics tools over MCP. The Verifier recomputes every number before the verified card replaces the template. Then the frame holds, like a TV replay, and the pitch shows why, drawn from the match data.

**[0:45.8, tour: split view]**
The same facts, told for different viewers: an analyst in English, a casual fan in Italian following a favourite player. The numbers and the seal never change.

**[0:55.6, tour: control room]**
In the control room, you watch the agents check each other. Here the Analyst credited two players who had already been substituted. The Verifier rejected it, and only the corrected version went on air.

**[1:08.2, evaluation report]**
We measured it on twenty unseen matches with hidden storylines the AI never sees. It found about half of them, with a precision of forty-three percent, and not a single unsupported number went on air. Every miss is in the public report.

**[1:22.7, Microsoft and Azure card]**
It runs on Azure Container Apps, Microsoft Foundry, PostgreSQL, Blob Storage and Application Insights; the voice is Azure AI Speech.

**[1:32.5, closing card]**
Regista. Reads the game, directs the broadcast.

Notes on accuracy (for the edit):
- "half of them found": recall 52 % (23 of 44) on 20 evaluation matches never used for tuning;
  10 control matches with nothing planted are scored separately (1.8 approved explanations
  per match).
- "not a single unsupported number went on air": 0 unsupported of 81
  approved; 267 evidence items recomputed independently, all confirmed; 45 items (xT, control
  index) are checked only by the Verifier's own recomputation.
- "this is where the team is now playing": the telestration in clip 04 is computed by code from
  the public match events of that window (`metrics/telestration.py`), not by a model.
- "≈ €1.76": total Microsoft Foundry spend of the project (prompt tuning, evaluation, recorded
  runs, production check), from the spend ledger in `STATUS.md`.
- The rejection in clip 06 comes from the official evaluation run of match m_5016 (pipeline at
  commit df03ba1); see the reviewer note shown in the clip.
- All clubs, players and data are synthetic.
