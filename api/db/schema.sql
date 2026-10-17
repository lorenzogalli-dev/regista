-- Idempotent schema. Later deliveries add moments, explanations, verdicts and overlays.
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    match_id    TEXT NOT NULL,
    seed        INTEGER NOT NULL,
    mode        TEXT NOT NULL CHECK (mode IN ('live', 'recorded')),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
