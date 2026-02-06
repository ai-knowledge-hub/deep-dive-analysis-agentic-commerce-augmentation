CREATE TABLE IF NOT EXISTS validation_jobs (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT,
    status TEXT NOT NULL,
    input_payload_json TEXT,
    requested_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS validation_results (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    structured_result_json TEXT,
    raw_response_text TEXT,
    score REAL,
    winner_id TEXT,
    evidence_strength TEXT,
    latency_ms INTEGER,
    cost_usd REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES validation_jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_validation_jobs_client ON validation_jobs(client_id);
CREATE INDEX IF NOT EXISTS idx_validation_jobs_entity ON validation_jobs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_validation_jobs_created ON validation_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_validation_results_job ON validation_results(job_id);
