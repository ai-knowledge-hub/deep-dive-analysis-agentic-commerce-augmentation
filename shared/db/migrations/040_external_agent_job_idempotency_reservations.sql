CREATE TABLE IF NOT EXISTS external_agent_job_idempotency_reservations (
    client_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (client_id, principal_id, idempotency_key),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

INSERT OR IGNORE INTO external_agent_job_idempotency_reservations (
    client_id,
    principal_id,
    idempotency_key,
    request_hash,
    created_at
)
SELECT
    client_id,
    principal_id,
    idempotency_key,
    request_hash,
    created_at
FROM external_agent_jobs;
