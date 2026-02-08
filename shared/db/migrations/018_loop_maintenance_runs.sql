CREATE TABLE IF NOT EXISTS loop_maintenance_runs (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    lookback_days INTEGER NOT NULL,
    min_confidence REAL NOT NULL,
    calibration_profiles_updated INTEGER NOT NULL DEFAULT 0,
    memory_artifacts_distilled INTEGER NOT NULL DEFAULT 0,
    triggered_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_loop_maintenance_runs_client
ON loop_maintenance_runs(client_id, created_at DESC);
