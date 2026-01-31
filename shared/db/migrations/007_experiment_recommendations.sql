CREATE TABLE IF NOT EXISTS experiment_recommendations (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    recommendation_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_experiment_recommendations_experiment
ON experiment_recommendations(experiment_id);
