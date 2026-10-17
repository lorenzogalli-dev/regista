# Metrics engine performance (D2.1)

Measured on 2026-10-18 with `uv run python -m metrics.bench m_1000 --speed 20 --seconds 60`
(Apple M4 laptop, Python 3.12, single process).

The benchmark replays dev match `m_1000` from minute 30 at 20x real time (200 tracking frames
per wall second, every frame ingested, not the decimated client stream). Per frame it measures
JSON parsing plus `MatchStore.ingest_frame`; once per wall second it runs `get_moment_context`
and a 15-minute `get_window_stats`.

| measure | value |
|---|---|
| frames ingested | 12,001 in 60.0 s (200.0 per wall second) |
| frame budget at 20x | 5.0 ms |
| frame parse + ingest, p50 | 0.087 ms |
| frame parse + ingest, p99 | 0.265 ms |
| frame parse + ingest, max | 14.0 ms (single outlier) |
| event parse + ingest, p50 / p99 | 0.032 / 0.463 ms |
| tool queries per wall second | 1 (moment context + 15-min window stats) |
| tool query time, p50 / max | 8.2 / 11.9 ms |
| max lag behind schedule | 12.9 ms |

The per-frame cost is about 2 % of the budget at 20x. Agent latency (D3) will dominate.
