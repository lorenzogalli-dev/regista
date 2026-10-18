# D5a: design system and hero frame

Review material for the look of the broadcast package (DESIGN.md §7). Everything shown is a
recorded clip of generated match `m_1000` (70:00–70:15, second half): tracking, events and all
numbers come from the simulator and the metrics tools (`python -m metrics.export_sample`). The
moment card text is hand-written and labelled **Design sample**: agents do not exist yet (D3).

| File | What |
|---|---|
| `broadcast-1920x1080.png` | Hero frame at 70:08: scorebug, player tag, pass trail + pass card (tier 0), AI moment card with verified seal (tier 1) |
| `broadcast-1440x900.png` | Same frame on a 1440×900 screen (the 16:9 stage is scaled and letterboxed) |
| `broadcast-hero.mp4` | 15 s at 30 fps, real-time capture: tag, pass trail, pass card count-up, receiver tag, moment card, seal stamp |
| `graphics-transparent-1920x1080.png` | `/graphics` output: overlay layer only, transparent PNG (for OBS / vision mixers) |
| `projection-check-1920x1080.png` | Magenta DOM markers on the canvas penalty and centre spots (`&debug=anchors`) |
| `design-1440.png`, `design-390.png` | `/design` reference page: tokens, type, team colours over clashing kits, components |

Reproduce (Vite on :5173, `cd web && npm run dev`):

```sh
node scripts/capture.mjs shot  "http://localhost:5173/broadcast?sample=hero_m_1000&t=4268900" out.png 1920 1080 3000
node scripts/capture.mjs video "http://localhost:5173/broadcast?sample=hero_m_1000" out.mp4 15
node scripts/capture.mjs audit "http://localhost:5173/broadcast?sample=hero_m_1000&t=4268900"
```

## Self-review against DESIGN.md before showing

Automated (`capture.mjs audit`, real-time, run at 7 points of the clip): every graphic inside
title-safe, nothing overlapping the scorebug or another graphic, text contrast ≥ 4.5:1, tabular
figures on all numbers, every panel skewed by exactly −5°. Final run: no problems.

Fixed during the review:
- **Title-safe:** the −5° skew pushed the moment card's bottom-left corner 14–26 px out of
  title-safe (scorebug 13 px). Panels now skew around their bottom-left corner, and the wipe slides
  in from the right, so the left edge never crosses the margin during the animation.
- **Scaled frame in screenshots:** headless Chrome's viewport was 993 px high, so the stage was
  scaled to 0.92 with black bars. The capture script sets the viewport explicitly.
- **Frozen animations in screenshots:** Chrome's virtual-time mode left motion's delayed
  animations half-way (seal at 1.8×, faded headline). Screenshots, audit and video now run in
  real time through the DevTools protocol.
- **Skew consistency:** shirt-number chips and the "AI insight" label were upright rectangles
  inside slanted panels, and the seal was rotated −4° instead of skewed. Chips now use a 5°
  parallelogram cut, and the seal is skewed −5° like everything else.
- **Overlap:** at 70:07 the receiver's tag touched the pass card. Tags now drop below the player
  when they would collide with a panel; the audit checks graphic-on-graphic overlap.
- **Headline orphan:** "PITCH" wrapped alone; headlines use balanced wrapping.
- **Player discs** enlarged (0.95 → 1.15 m) so shirt numbers stay legible.
- **/design at 390 px:** the broadcast components overflowed their grid cells; they now scale
  to the column width (no horizontal scroll). Type specimens overlapped at 1440 px; fixed line
  height and columns.

Known limits of D5a (for D5b): no momentum ribbon, stat compare, shot speed, lower third,
caption or recap yet; no template → model text morph or amber pending state; the pitch is a
fixed camera; team colours of the sample are gold/black vs white/red, the clash cases are on
`/design`.
