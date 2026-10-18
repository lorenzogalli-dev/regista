-- Idempotent schema. Later deliveries add moments, explanations, verdicts and overlays.
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    match_id    TEXT NOT NULL,
    seed        INTEGER NOT NULL,
    mode        TEXT NOT NULL CHECK (mode IN ('live', 'recorded')),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

-- D3: agent runs. A recorded agent run is a saved pipeline output, replayed with zero model calls.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS pipeline_mode TEXT;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS cost_eur DOUBLE PRECISION;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS summary JSONB;

CREATE TABLE IF NOT EXISTS run_moments (
    run_id    TEXT NOT NULL REFERENCES runs (run_id) ON DELETE CASCADE,
    moment_id TEXT NOT NULL,
    t_ms      INTEGER NOT NULL,
    status    TEXT NOT NULL,
    data      JSONB NOT NULL,
    PRIMARY KEY (run_id, moment_id)
);
