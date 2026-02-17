CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    experiment_id TEXT,
    objective_json TEXT,
    allowed_capabilities_json TEXT,
    capability_versions_json TEXT,
    budgets_json TEXT,
    approval_policy_json TEXT,
    requires_approval INTEGER DEFAULT 1,
    state TEXT DEFAULT 'battery_ready',
    status TEXT DEFAULT 'queued',
    error_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat_at TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_client ON agent_runs(client_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_experiment ON agent_runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created ON agent_runs(created_at);

CREATE TABLE IF NOT EXISTS agent_actions (
    id TEXT PRIMARY KEY,
    agent_run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    status TEXT NOT NULL,
    capability_name TEXT NOT NULL,
    capability_version TEXT,
    inputs_json TEXT,
    outputs_json TEXT,
    inputs_hash TEXT,
    outputs_hash TEXT,
    rationale_text TEXT,
    confidence REAL,
    snapshot_version INTEGER,
    hypothesis_id TEXT,
    variant_id TEXT,
    validation_job_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    error_text TEXT,
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE SET NULL,
    FOREIGN KEY (validation_job_id) REFERENCES validation_jobs(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_actions_run_sequence
ON agent_actions(agent_run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_agent_actions_run_status
ON agent_actions(agent_run_id, status, created_at);

