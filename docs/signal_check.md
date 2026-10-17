# Storyline signal check - after strengthening (2026-10-18)

Produced by `uv run python -m eval.signal_check --mode final` (tables 1-3) and `--mode tune` (table 4).
Before: `docs/signal_check_before.md`.

Protocol
- Simulator changes were tuned only on calibration seeds 2000-2099 (noise: 2200-2249), in three rounds.
- The judged table (2100-2199) and the false-alarm table (2250-2299) were computed once, after the third round.
- Dev seeds (1000-1019) are a control only (4-10 storylines per type).
- Pass criteria per type: median full-window z in [2, 5], >= 70 % of storylines above the noise p95,
  median 2-minute slice z < 1.5. z uses the mean and standard deviation of noise windows of the same length.

Decisions
- Pass on the judged seeds: momentum_shift, tactical_switch/long_ball, tactical_switch/wide, player_arc.
- pressing_spell (median z 1.79) and fatigue_drop (1.75) did not pass and are below 2: they are implemented
  but disabled in the generator (`sim/storylines.py: ACTIVE_TYPES`). Their absolute effects are large
  (e.g. PPDA in pressing windows about 3.6 vs 12.9 elsewhere on tuning seeds), but 12-20 minute windows of a
  no-storyline match vary as much (field tilt sd 0.175, PPDA heavy-tailed), so they are not reliably
  distinguishable from noise with these signals.
- No type is kept as "difficult" (none failed with median z >= 2).

Changes after the judged run (plausibility only, signal mechanisms untouched): shot rate and conversion,
3-5-2 wing-back and midfield anchors, a red-card storyline player is no longer substituted before the card.
Table 4 re-checks the active types on the tuning seeds after those changes.

### Judged on calibration seeds 2100-2199 (noise 2200-2249)

| type | n | z median | detected (>p95) | >=2 signals over own p95 | 2-min slice z median | per-signal z median | pass |
|---|---|---|---|---|---|---|---|
| pressing_spell | 37 | 1.79 | 86% | 43% | 0.28 | ppda 0.88, pass_completion 3.38, field_tilt 1.04 | NO |
| fatigue_drop | 41 | 1.75 | 66% | 44% | 0.28 | top_speed 2.85, sprint_count 1.09, flank_attack_share 0.78 | NO |
| momentum_shift | 35 | 2.15 | 83% | 43% | 0.80 | possession 1.54, field_tilt 2.87 | yes |
| tactical_switch/long_ball | 26 | 2.34 | 88% | 42% | 0.54 | avg_pass_length 3.08, pass_completion 1.62 | yes |
| tactical_switch/wide | 27 | 4.00 | 96% | n/a | 1.09 | width 4.00 | yes |
| player_arc | 40 | 4.13 | 92% | 70% | 1.05 | progressive_passes 5.43, touches 2.78 | yes |

### Control: dev seeds 1000-1019 (noise 2200-2249)

| type | n | z median | detected (>p95) | >=2 signals over own p95 | 2-min slice z median | per-signal z median | pass |
|---|---|---|---|---|---|---|---|
| pressing_spell | 6 | 1.18 | 67% | 17% | 0.01 | ppda 0.83, pass_completion 2.23, field_tilt 0.50 | NO |
| fatigue_drop | 9 | 1.62 | 67% | 33% | 0.17 | top_speed 2.77, sprint_count 1.28, flank_attack_share -0.02 | NO |
| momentum_shift | 8 | 2.16 | 75% | 38% | 0.78 | possession 1.46, field_tilt 2.86 | yes |
| tactical_switch/long_ball | 6 | 3.79 | 100% | 67% | 1.00 | avg_pass_length 5.33, pass_completion 2.03 | yes |
| tactical_switch/wide | 6 | 3.62 | 100% | n/a | 0.74 | width 3.62 | yes |
| player_arc | 7 | 3.72 | 100% | 57% | 0.86 | progressive_passes 4.98, touches 2.22 | yes |

### False alarms on held-out no-storyline matches (2250-2299)

| type | rule | window (min) | share of windows | episodes / match | matches with any |
|---|---|---|---|---|---|
| pressing_spell | combined score > p95 | 17 | 5.2% | 0.90 | 70% |
| pressing_spell | >=2 signals over own p95 | 17 | 1.4% | 0.30 | 28% |
| fatigue_drop | combined score > p95 | 18 | 4.7% | 1.78 | 90% |
| fatigue_drop | >=2 signals over own p95 | 18 | 0.5% | 0.44 | 34% |
| momentum_shift | combined score > p95 | 17 | 4.4% | 0.74 | 60% |
| momentum_shift | >=2 signals over own p95 | 17 | 1.3% | 0.36 | 34% |
| tactical_switch/long_ball | combined score > p95 | 19 | 6.4% | 0.74 | 62% |
| tactical_switch/long_ball | >=2 signals over own p95 | 19 | 0.5% | 0.16 | 16% |
| tactical_switch/wide | combined score > p95 | 19 | 4.4% | 0.74 | 58% |
| player_arc | combined score > p95 | 21 | 5.3% | 1.36 | 88% |
| player_arc | >=2 signals over own p95 | 21 | 1.7% | 0.68 | 54% |

### 4. Post-change sanity check: tuning seeds 2000-2099 (noise 2200-2249)


| type | n | z median | detected (>p95) | >=2 signals over own p95 | 2-min slice z median | per-signal z median | pass |
|---|---|---|---|---|---|---|---|
| pressing_spell | 0 | - | - | - | - | - | - |
| fatigue_drop | 0 | - | - | - | - | - | - |
| momentum_shift | 66 | 2.98 | 91% | 64% | 0.99 | possession 2.18, field_tilt 3.64 | yes |
| tactical_switch/long_ball | 32 | 2.15 | 75% | 44% | 0.60 | avg_pass_length 2.60, pass_completion 1.55 | yes |
| tactical_switch/wide | 38 | 4.41 | 97% | n/a | 1.21 | width 4.41 | yes |
| player_arc | 67 | 3.53 | 88% | 73% | 0.79 | progressive_passes 3.95, touches 2.91 | yes |
