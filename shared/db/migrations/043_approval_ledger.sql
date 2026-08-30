CREATE TABLE IF NOT EXISTS approval_records (
    approval_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    current_sequence INTEGER NOT NULL,
    current_status TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    envelope_digest TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tenant_id) REFERENCES clients(id) ON DELETE RESTRICT,
    FOREIGN KEY (workflow_id) REFERENCES agent_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, approval_id)
);

CREATE INDEX IF NOT EXISTS idx_approval_records_action
    ON approval_records(tenant_id, workflow_id, action_id, updated_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_records_one_lineage_per_action
    ON approval_records(tenant_id, workflow_id, action_id);

CREATE TABLE IF NOT EXISTS approval_commands (
    command_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    command_version TEXT NOT NULL,
    principal_type TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    authority_source TEXT NOT NULL,
    authority_version TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    expected_sequence INTEGER,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL,
    result_hash TEXT NOT NULL,
    first_event_sequence INTEGER NOT NULL,
    last_event_sequence INTEGER NOT NULL,
    received_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES clients(id) ON DELETE RESTRICT,
    FOREIGN KEY (workflow_id) REFERENCES agent_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id) ON DELETE RESTRICT,
    FOREIGN KEY (approval_id) REFERENCES approval_records(approval_id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_approval_commands_approval
    ON approval_commands(tenant_id, workflow_id, approval_id, completed_at DESC);

CREATE TABLE IF NOT EXISTS approval_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL,
    status TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    envelope_digest TEXT NOT NULL,
    command_id TEXT NOT NULL,
    event_index INTEGER NOT NULL,
    principal_type TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    authority_source TEXT NOT NULL,
    authority_version TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tenant_id) REFERENCES clients(id) ON DELETE RESTRICT,
    FOREIGN KEY (workflow_id) REFERENCES agent_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id) ON DELETE RESTRICT,
    FOREIGN KEY (approval_id) REFERENCES approval_records(approval_id) ON DELETE RESTRICT,
    FOREIGN KEY (command_id) REFERENCES approval_commands(command_id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, approval_id, sequence),
    UNIQUE (tenant_id, workflow_id, command_id, event_index)
);

CREATE INDEX IF NOT EXISTS idx_approval_events_action
    ON approval_events(tenant_id, workflow_id, action_id, recorded_at ASC);

CREATE TRIGGER IF NOT EXISTS approval_events_no_update
BEFORE UPDATE ON approval_events
BEGIN
    SELECT RAISE(ABORT, 'approval events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS approval_events_no_delete
BEFORE DELETE ON approval_events
BEGIN
    SELECT RAISE(ABORT, 'approval events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS approval_commands_no_update
BEFORE UPDATE ON approval_commands
BEGIN
    SELECT RAISE(ABORT, 'approval command receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS approval_commands_no_delete
BEFORE DELETE ON approval_commands
BEGIN
    SELECT RAISE(ABORT, 'approval command receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS approval_records_no_delete
BEFORE DELETE ON approval_records
BEGIN
    SELECT RAISE(ABORT, 'approval records cannot be deleted');
END;
