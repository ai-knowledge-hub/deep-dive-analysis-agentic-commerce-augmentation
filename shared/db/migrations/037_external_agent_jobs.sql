CREATE TABLE IF NOT EXISTS external_agent_jobs (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    agent_profile_id TEXT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    requested_skill_id TEXT,
    requested_tool_id TEXT,
    status TEXT NOT NULL DEFAULT 'accepted',
    trace_id TEXT,
    request_json TEXT NOT NULL DEFAULT '{}',
    response_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    UNIQUE (client_id, principal_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_external_agent_jobs_client_created
ON external_agent_jobs(client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_external_agent_jobs_principal_created
ON external_agent_jobs(client_id, principal_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_external_agent_jobs_trace
ON external_agent_jobs(trace_id, created_at DESC);
