ALTER TABLE experiments
ADD COLUMN protocol_snapshot_version INTEGER DEFAULT 0;

CREATE TABLE IF NOT EXISTS experiment_retrieval_snapshots (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    battery_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    snapshot_version INTEGER NOT NULL,
    retrieval_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (battery_id) REFERENCES query_batteries(id) ON DELETE CASCADE,
    FOREIGN KEY (query_id) REFERENCES query_battery_queries(id) ON DELETE CASCADE,
    UNIQUE (experiment_id, query_id, snapshot_version)
);

CREATE INDEX IF NOT EXISTS idx_experiment_retrieval_snapshots_experiment_version
ON experiment_retrieval_snapshots(experiment_id, snapshot_version, created_at);

CREATE TABLE IF NOT EXISTS experiment_hypotheses (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    snapshot_version INTEGER NOT NULL,
    statement_json TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    source TEXT DEFAULT 'retrieval_gap',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_experiment_hypotheses_experiment_version
ON experiment_hypotheses(experiment_id, snapshot_version, created_at);

ALTER TABLE experiment_variants
ADD COLUMN hypothesis_id TEXT;

ALTER TABLE experiment_variants
ADD COLUMN provenance_json TEXT;

ALTER TABLE experiment_runs
ADD COLUMN snapshot_version INTEGER;

ALTER TABLE experiment_runs
ADD COLUMN hypothesis_id TEXT;
