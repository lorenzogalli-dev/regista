# Storyline signal check — before strengthening (2026-10-18)

Simulator as of commit 77dc973. Produced by `uv run python -m eval.signal_check`.
Criteria per type: median full-window z in [2, 5], >= 70 % of storylines above the noise p95, median 2-minute slice z < 1.5.


### Dev seeds 1000–1019 (noise: calibration-control 2200–2249)

| type | n | z median | detected (>p95) | 2-min slice z median | per-signal z median | pass |
|---|---|---|---|---|---|---|
| pressing_spell | 10 | 0.41 | 20% | 0.06 | ppda 0.35, pass_completion 0.73, field_tilt 0.59 | NO |
| fatigue_drop | 9 | 0.60 | 33% | 0.18 | top_speed 0.49, sprint_count -0.02, flank_attack_share 1.02 | NO |
| momentum_shift | 8 | 1.34 | 25% | 0.95 | possession 1.85, field_tilt 0.65 | NO |
| tactical_switch/long_ball | 4 | -0.81 | 0% | -0.29 | avg_pass_length -0.44, pass_completion -0.52 | NO |
| tactical_switch/wide | 7 | 2.01 | 57% | 0.42 | width 2.01 | NO |
| player_arc | 9 | 2.35 | 56% | 0.60 | progressive_passes 2.44, touches 1.26 | NO |

### Calibration seeds 2000–2199 (noise: calibration-control 2200–2249)

| type | n | z median | detected (>p95) | 2-min slice z median | per-signal z median | pass |
|---|---|---|---|---|---|---|
| pressing_spell | 96 | 0.77 | 32% | 0.12 | ppda 0.65, pass_completion 1.22, field_tilt 0.64 | NO |
| fatigue_drop | 80 | 1.17 | 50% | 0.26 | top_speed 1.81, sprint_count 0.72, flank_attack_share 0.96 | NO |
| momentum_shift | 93 | 1.36 | 45% | 0.62 | possession 1.40, field_tilt 1.28 | NO |
| tactical_switch/long_ball | 41 | 0.67 | 22% | 0.19 | avg_pass_length 0.44, pass_completion 0.55 | NO |
| tactical_switch/wide | 57 | 1.53 | 49% | 0.53 | width 1.53 | NO |
| player_arc | 91 | 1.58 | 56% | 0.39 | progressive_passes 1.88, touches 1.06 | NO |

### False alarms on held-out no-storyline matches (2250–2299)

| type | window (min) | windows | share > p95 | episodes / match | matches with any |
|---|---|---|---|---|---|
| pressing_spell | 12 | 5390 | 5.1% | 1.44 | 90% |
| fatigue_drop | 18 | 13040 | 4.8% | 1.70 | 94% |
| momentum_shift | 12 | 5390 | 6.8% | 1.78 | 88% |
| tactical_switch/long_ball | 15 | 4790 | 5.2% | 0.94 | 72% |
| tactical_switch/wide | 15 | 4790 | 4.8% | 1.12 | 84% |
| player_arc | 21 | 9972 | 4.9% | 1.36 | 90% |
