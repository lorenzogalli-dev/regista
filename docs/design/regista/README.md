# Regista: UX and design review (2026-10-18)

Review material for the pre-submission revision: rename to **Regista**, new landing, guided
tour, broadcast player (timeline, next key moment, auto-skip, moment replay with telestration,
insights feed, evidence behind the seal), new type and accent. Rules: `DESIGN.md` (§2, §5, §5b,
§6). Everything shown is the real app replaying recorded agent runs of synthetic matches.

| File | What |
|---|---|
| `guided-tour.mp4` | The full guided tour, real time, 124 s at 1920×1080 (the backbone of the demo video) |
| `landing-1920.png` | Landing above the fold: tagline, one line, name line, the real broadcast playing, "Take the 2-minute tour" |
| `landing-1440-full.png`, `landing-390-full.png` | Whole landing: problem, what it does, trust schema, results with caveats, explore, under the hood |
| `moment-replay-territory-1920.png` | Moment replay: held frame, "Moment replay" bug, final third shaded with the team's final-third actions, insights feed, timeline |
| `moment-replay-press-1920.png` | Telestration "where they win it back": regain locations and the zone they cluster in |
| `moment-replay-progressive-1440.png` | Telestration "progressive passes": the player ringed, his progressive passes as arrows |
| `moment-replay-width-1440.png` | Telestration "play out wide": both wide channels, passes and carries that start there |
| `moment-replay-long-passes-1920.png` | Telestration "longest passes" in the window |
| `tour-evidence-1920.png` | The seal's evidence panel: before/after bars for every cited metric, "recomputed independently by code" |
| `tour-control-room-1920.png` | Control room in the tour, with the authentic Verifier rejection |
| `player-skip-quiet-play-1920.png` | "Skipping quiet play ×8", empty insights feed with "jump to the first one" |
| `player-390.png` | Player at 390 px: programme, playback, timeline, insights feed |

Reproduce (API on :8000, `cd web && npm run dev`):

```sh
node scripts/capture.mjs shot "http://localhost:5173/broadcast?run=r_m_1000_1ad2f33e&from=2049000" out.png 1920 1080 9500
node scripts/capture.mjs video "http://localhost:5173/tour" tour.mp4 124 1920 1080
./scripts/audit.sh
```

## Layout audit

`web/scripts/audit.sh` runs the design audit (`web/src/broadcast/audit.ts`) at 1920×1080,
1440×900 and 390×844 on the player during moment replays with each kind of telestration
(territory, press, progressive passes, long passes, width), in normal play, and on the tour with
the evidence panel open. It checks title-safe, overlaps between graphics (now including the
telestration label, the replay bug and the evidence panel), overlap with the scorebug, text
contrast ≥ 4.5:1, tabular figures, the −5° skew, and, outside the programme, no horizontal
scroll and the insights feed, timeline and header inside the viewport. Final run: 21 audits,
no problems.

Found and fixed during the review:
- **Team short names under 4.5:1** on the momentum ribbon and stat compare for dark kits (green
  `#1E7F4F` 3.56:1, purple 2.97:1): they used the team's mark colour (≥ 3:1). Text now uses
  `TeamColors.text`, lightened to ≥ 4.5:1 on the panel.
- **Pass progression "+-10.2 m"** for backward passes: the sign is now formatted with the value.
- **Telestration label wrapping** ("last 15 / min"): one line, width from the text.
- **"Continue" over the source label / telestration label**: moved out of the programme into
  the playback bar.
- **Tour pacing**: the verified-card caption showed for under a second before the replay; the
  replay is now told in three beats (verified card, telestration, evidence) with a longer hold.

## Type and accent

- Display **Barlow Condensed**, body **Barlow**, editorial line **Newsreader** italic, all SIL
  OFL, self-hosted with their licences in `web/public/fonts/LICENSES`. Archivo and Inter are
  removed.
- Accent **Regista green `#7CF25C`** in place of the earlier yellow: 13.5:1 on the background,
  ΔE 68 from the AI cyan, ΔE ≥ 57 from every team kit colour in the generated matches. Green is
  "computed by code" and product chrome; cyan stays reserved for agent-written content. The
  yellow still visible on the pitch in match m_1000 is the kit colour of the (synthetic) home
  team, not an accent.
