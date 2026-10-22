# Regista — Design Direction

> Replaces and extends SPEC §8. The quality bar is **broadcast-grade**: every screen should look like it could go on air tonight. Polish here is not decoration; "User Experience & Presentation" is 20 % of the score and the demo video is judged on it.

## 1. Concept

**"Verified on air."** The product is a broadcast graphics engine whose AI never puts an unverified claim on screen. The visual language makes that visible:

- **Data graphics** (tier 0, computed by code): clean, neutral, instant.
- **AI insight graphics** (tier 1, written by agents): a distinct accent colour and a small **verified seal** showing how many evidence items passed (e.g. `✓ 3/3`). Tapping it opens the evidence.

A viewer should be able to tell at a glance which graphics are measurements and which are interpretations. That is the core idea of the project, expressed in pixels.

## 2. Identity

- Product name **Regista**, tagline **"Reads the game. Directs the broadcast."** Wordmark: a slanted green tab with a "go on air" notch, then the name in Barlow Condensed 800 (`web/src/brand/Wordmark.tsx`, `web/public/regista-icon.svg`, also the favicon). The name line, used on the landing and in the README: "In Italian, regista is both the playmaker who reads the game and the TV director who decides what goes on air."
- **No real league, club, broadcaster or sponsor marks, and no proprietary broadcast fonts.** No code, assets, logos or text from any other product.

### Type (Google Fonts, SIL OFL, self-hosted under `web/public/fonts`)
- **Barlow Condensed** (500–800) for everything display: scorebug, lower thirds, headlines, big numbers, titles.
- **Barlow** (400–700) for body text and UI controls.
- **Newsreader** italic for the odd editorial line (the name line on the landing). Never on the broadcast layer.
- Tabular figures everywhere numbers change (`font-variant-numeric: tabular-nums`) so values never jitter.

### Colour
- Base: night-stadium dark. Near-black with a green cast (`#06110C` background, `#0C1B14` panels), pitch rendered in deep desaturated greens with subtle mowing stripes.
- Text: off-white `#F2F5F3`, secondary `#9FB0A7`.
- **Team colours drive accents dynamically** (from `match.json`); every component must look good with any pair of team colours (test with at least 4 clashing combinations, enforce contrast automatically).
- **AI insight accent**: one reserved colour not used for any team or data graphic: electric cyan `#46E5D8`. Used only for agent-written content and the verified seal.
- **Brand accent: Regista green `#7CF25C`** (replaces the earlier yellow/amber highlights in the product chrome). Used for the wordmark, primary buttons, eyebrows, the played part of the timeline, data-graphic ("computed by code") marks and the telestration, which is drawn by code from the match data. Never on agent-written text. Checked: contrast 13.5:1 on the background, ΔE 68 from the AI cyan, ΔE ≥ 57 from every team kit colour in the generated matches.
- Team colours used as **text** (short names on the ribbon and stat compare) are lightened until they reach 4.5:1 on the panel (`TeamColors.text`); `line` (≥ 3:1) is for marks only.
- Status: amber for "pending model text" (template shown), red only for errors in the control room.
- Light theme not required; dark is the product. The site pages alternate dark grey and chalk bands (§5c); the broadcast layer stays dark. Respect `prefers-reduced-motion`.

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
4. **Control room**: the "gallery" behind the broadcast. Live agent pipeline as a node graph (Detector → Analyst → Verifier → Narrator / Persona → Director), each moment flowing through, verifier verdicts, rejected claims in red with the reason, fallbacks in amber, latency per stage. Each moment in flight is a token that travels along the graph to the agent working on it (back to the Analyst in red on a retry, on to "On air" when published). This is where the multi-agent design becomes visible on video.
5. **Eval report**: storyline recall, precision, evidence validity, false alarms on control seeds, latency, as a designed page (not a raw table).
6. **Recap page**: simple.
7. **Landing** (plain English, no jargon above the fold, no real club or player names): hero (tagline, one line, name line, the real broadcast playing a recorded run, primary action **Take the 2-minute tour**); the problem; what it does (three cards: live stats graphics / tactical explanations / made for every fan, each labelled "computed by code" or "written by AI, verified"); why you can trust it, with an animated schema (hidden storyline → AI watches blind → found or false alarm); results as big counting numbers with the caveats in small type and a link to the report; explore (one card per screen, one sentence each); under the hood for experts (animated pipeline and the Microsoft technologies, one line each).
8. **Guided tour** (`/tour`, ≈ 2 min, the landing's main action and the backbone of the demo video): intro → pass card → top speed → shot speed → template → verified AI card → moment replay with telestration and the evidence → split view → control room with the authentic Verifier rejection → results. Each scene carries a caption with who made what is on screen: **Code** (green), **AI agent · verified** (cyan) or both.

Every replay is labelled **"Recorded agent run"**, live sessions **"Live"**.

## 5b. Watching a match (broadcast player)

Nobody watches 90 minutes, and an AI card that wipes out while the match runs cannot be read.

- **Timeline** under the programme: AI insights (cyan diamonds, tier 1) and data graphics (green ticks, tier 0) on separate lanes, plus goals, shots, red cards and Verifier rejections (red cross). Click a marker to go to just before it; click the track to seek; ←/→ move 30 s.
- **Next key moment** (button and **N**): about 20 s before the next AI insight, goal, red card or rejection.
- **Skip quiet play** (on by default, can be turned off): when nothing is on air and the next marker is more than 25 s away, the match runs at ×8 until 6 s before it, with a visible "Skipping quiet play ×8" indicator.
- **Moment replay** (on by default, can be turned off): when a verified card goes on air, the match slows down and holds like a TV replay. The hold lasts the card's reading time (about 4 words a second plus 2 s, at least 6 s, at most 16 s), with a "Moment replay" bug and its progress bar; Space or **Continue** plays on.
- **Telestration** during the replay, from the match data (code, green): the zone where the team wins the ball back, the wide channels, its longest passes, a player's progressive passes or its final-third actions, the cited players ringed, and a "From the data" label with the count. It shows the why, not only says it.
- **Insights feed** beside the programme: every card that has gone on air stays readable, in the chosen persona; its seal opens the evidence; "Watch this moment again" goes back to the template.
- **The ✓ seal opens the evidence**: for every metric cited, before and after bars with the subject and windows, and the line "Recomputed independently by code from the match data before it went on air."
- The programme keeps every rule above (title-safe, no overlap, contrast, skew); the player chrome lives outside the 16:9 frame. `&clean=1` gives the bare programme.

## 5c. Site pages (landing, eval report, architecture, recap)

The pages around the product, styled like a matchday site rather than an app (revision of 2026-10-22, `web/src/routes/site.css`).

- **Pill nav**: centred, fully rounded, semi-transparent dark glass with backdrop blur, fixed at the top; wordmark, section or page links (hidden under 860 px), and a dark green **▶ Tour** button (`#1F7A14`, white text 5.5:1).
- **Bands**: full-width sections alternating dark grey `#15181A` (panels `#1E2225`) and chalk `#E8E9E2` with faint mowing stripes, like the paint and the grass. On chalk: ink `#121513` (15:1), secondary `#4A524C` (6.6:1) and a darker brand green `#1D6B12` (5.4:1) for eyebrows and accents; dark panels inside a chalk band (`.dark-scope`) keep the dark palette. Inner pages open with a chalk header band.
- **Football containers**: numbers on a **stadium scoreboard** (near-black dot-matrix board, green header strip with what is shown and two lamps); links on a **tactics board** (pitch green with mowing stripes and a corner arc); steps numbered with **shirt numbers** (round, green for code, cyan for agents, white for data and on-air).
- These rounded, softer shapes are for the site pages only; the broadcast layer keeps its sharp, slanted geometry (§2, §4).

## 6. Quality bar (definition of done for the front-end)

- 60 fps on a 2020+ laptop in the broadcast view; no layout shift when overlays arrive.
- Works at 1920×1080, 1440×900 and 390 px wide (second screen, player, landing, tour). `web/scripts/audit.sh` checks the broadcast player (with each kind of telestration, the replay bug, the insights feed and the timeline) and the tour (with the evidence panel open) at all three sizes: title-safe, overlaps, contrast, tabular figures, skew, no horizontal scroll.
- Motion respects `prefers-reduced-motion` everywhere (count-ups land on their value, pulses and flowing links stop, scroll reveals only fade).
- No graphic ever overlaps the scorebug or leaves title-safe.
- Contrast ≥ 4.5:1 for all text over any team colour pair.
- Screenshot of each screen reviewed by Lore before the delivery is closed.

## 7. Process

- **D5a — Design system + hero frame** (right after D2, using a generated sample match): tokens, type, colour, the scorebug, one data graphic, one AI moment card, the pitch render. Lore approves the look **before** the rest is built.
- **D5b — Full package and screens** after D3/D4.
- Iterate with screenshots: render, review against this document, fix, repeat. Do not declare done from code alone.
