# Ground Truth Football — Design Direction

> Replaces and extends SPEC §8. The quality bar is **broadcast-grade**: every screen should look like it could go on air tonight. Polish here is not decoration; "User Experience & Presentation" is 20 % of the score and the demo video is judged on it.

## 1. Concept

**"Verified on air."** The product is a broadcast graphics engine whose AI never puts an unverified claim on screen. The visual language makes that visible:

- **Data graphics** (tier 0, computed by code): clean, neutral, instant.
- **AI insight graphics** (tier 1, written by agents): a distinct accent colour and a small **verified seal** showing how many evidence items passed (e.g. `✓ 3/3`). Tapping it opens the evidence.

A viewer should be able to tell at a glance which graphics are measurements and which are interpretations. That is the core idea of the project, expressed in pixels.

## 2. Identity

- Fictional product name and wordmark only. **No real league, club, broadcaster or sponsor marks, and no proprietary broadcast fonts.**
- Visual identity must be **distinct from any of the author's other products**: different typeface, palette and shapes.

### Type (Google Fonts, open licence)
- **Archivo** (variable, width axis) for everything display: condensed widths for scorebug and lower thirds, expanded for big numbers and titles.
- **Inter** for body text and UI controls.
- Tabular figures everywhere numbers change (`font-variant-numeric: tabular-nums`) so values never jitter.

### Colour
- Base: night-stadium dark. Near-black with a green cast (`#06110C` background, `#0C1B14` panels), pitch rendered in deep desaturated greens with subtle mowing stripes.
- Text: off-white `#F2F5F3`, secondary `#9FB0A7`.
- **Team colours drive accents dynamically** (from `match.json`); every component must look good with any pair of team colours (test with at least 4 clashing combinations, enforce contrast automatically).
- **AI insight accent**: one reserved colour not used for any team or data graphic (proposal: electric cyan `#46E5D8`). Used only for agent-written content and the verified seal.
- Status: amber for "pending model text" (template shown), red only for errors in the control room.
- Light theme not required; dark is the product. Respect `prefers-reduced-motion`.

### Shape and material
- Sharp, slightly slanted geometry (4–6° skew on bars and tabs), like modern sports broadcast packages. No rounded "app card" look on the broadcast layer.
- Panels: dark glass (backdrop blur, 1 px inner highlight), never flat grey boxes.
- One grid for the 16:9 broadcast frame with title-safe margins (5 %), so graphics never touch the edges.

## 3. Motion

Motion is what makes it feel like TV.
- Graphics **wipe or slide in** along their slant (250–400 ms, ease-out), hold, then wipe out. Never fade alone.
- Numbers **count up** to their value; speed badges "tick" like a speedometer.
- Player tags follow the player smoothly (interpolate tracking between 10 Hz frames; target 60 fps).
- Pass trail: animated line from passer to receiver, its glow intensity proportional to pass difficulty.
- When agent text replaces a template, the text **morphs in place** (no layout jump) and the verified seal stamps in.
- Momentum ribbon flows continuously along the bottom.
- Library: `motion` (Framer Motion) for DOM/SVG graphics; pitch on canvas (or WebGL via a light library if needed) for 60 fps. Ask before adding anything heavier.

## 4. Broadcast graphics package (the "TV graphics")

All rendered from the overlay timeline (SPEC §6.2):

| Graphic | Tier | Description |
|---|---|---|
| **Scorebug** | 0 | Top-left: team shorts, score, clock, possession dot. Always on. |
| **Player tag** | 0 | Name + number following the player; appears on key involvement. |
| **Speed badge** | 0 | Pops next to a player when a speed threshold is crossed ("34.6 km/h"). |
| **Shot speed** | 0 | Ball speed on the shot with a speedometer tick, plus xG. |
| **Pass card** | 0 | Length, progression, difficulty meter (0–100) along the pass trail. |
| **Lower third — player** | 0 | Name, role, key stat of the match so far. |
| **Stat compare** | 0 | Two-team bar comparison (possession, field tilt, PPDA) with slanted bars in team colours. |
| **Momentum / control ribbon** | 0 | Bottom strip: control index over time, team-coloured. |
| **Moment card** | 1 | The headline: what happened + why it matters, verified seal, cyan accent. |
| **Caption / ticker** | 1 | One-line live narration. |
| **Half-time / full-time recap** | 1 | Full-frame graphic with 3 key moments and verified explanations. |

### Graphics-only output (production path)
A route `/graphics?match=…&persona=…` renders **only** the overlay layer on a **transparent background** at 1920×1080, synced to match time. It can be dropped as a browser source into OBS or a vision mixer over any feed. Show this once in the demo video: it is the bridge between "web app" and "real broadcast".

## 5. Screens

1. **Broadcast view** (hero, 16:9): the pitch shot with the full graphics package. The pitch is a top-down 2D render with a **slight perspective tilt** (CSS 3D or WebGL) so it reads like a high camera, not a diagram.
2. **Split view**: same moment, two personas side by side (e.g. Analyst EN | Casual IT, favourite player). The centrepiece of the video.
3. **Second screen (mobile)**: vertical feed for a fan: moment cards, favourite-player tracker, language switch. Must look great at 390 px.
4. **Control room**: the "gallery" behind the broadcast. Live agent pipeline as a node graph (Detector → Analyst → Verifier → Narrator / Persona → Director), each moment flowing through, verifier verdicts, rejected claims in red with the reason, fallbacks in amber, latency per stage. This is where the multi-agent design becomes visible on video.
5. **Eval report**: storyline recall, precision, evidence validity, false alarms on control seeds, latency, as a designed page (not a raw table).
6. **Recap page**: simple.
7. **Landing**: one screen: product name, one-sentence pitch, "Watch a recorded match" / "Go live" (live quota shown), link to the control room.

Every replay is labelled **"Recorded agent run"**, live sessions **"Live"**.

## 6. Quality bar (definition of done for the front-end)

- 60 fps on a 2020+ laptop in the broadcast view; no layout shift when overlays arrive.
- Works at 1920×1080, 1440×900 and 390 px wide (second screen).
- No graphic ever overlaps the scorebug or leaves title-safe.
- Contrast ≥ 4.5:1 for all text over any team colour pair.
- Screenshot of each screen reviewed by Lore before the delivery is closed.

## 7. Process

- **D5a — Design system + hero frame** (right after D2, using a generated sample match): tokens, type, colour, the scorebug, one data graphic, one AI moment card, the pitch render. Lore approves the look **before** the rest is built.
- **D5b — Full package and screens** after D3/D4.
- Iterate with screenshots: render, review against this document, fix, repeat. Do not declare done from code alone.
