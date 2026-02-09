CREATE TABLE IF NOT EXISTS validation_callback_tokens (
    token_hash TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    provider_run_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES validation_jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_validation_callback_tokens_job
ON validation_callback_tokens(job_id, created_at DESC);
