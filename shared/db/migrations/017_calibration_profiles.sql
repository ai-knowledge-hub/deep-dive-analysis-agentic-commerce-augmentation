CREATE TABLE IF NOT EXISTS calibration_profiles (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    provider TEXT NOT NULL,
    metric_weights_json TEXT,
    drift_score REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (client_id, brand_id, provider),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_calibration_profiles_scope
ON calibration_profiles(client_id, brand_id, provider);

CREATE INDEX IF NOT EXISTS idx_calibration_profiles_updated
ON calibration_profiles(updated_at);

