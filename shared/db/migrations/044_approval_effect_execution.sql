ALTER TABLE agent_actions ADD COLUMN approval_id TEXT;
ALTER TABLE agent_actions ADD COLUMN approval_envelope_digest TEXT;
ALTER TABLE agent_runs ADD COLUMN active_graph_revision INTEGER NOT NULL DEFAULT 1
    CHECK (active_graph_revision >= 1);

CREATE TABLE IF NOT EXISTS approval_effect_executions (
    execution_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    approval_envelope_digest TEXT NOT NULL,
    authorization_source_digest TEXT NOT NULL,
    effect_idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('started', 'uncertain', 'succeeded')
    ),
    receipt_id TEXT,
    outputs_hash TEXT,
    error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES clients(id) ON DELETE RESTRICT,
    FOREIGN KEY (workflow_id) REFERENCES agent_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id) ON DELETE RESTRICT,
    FOREIGN KEY (approval_id) REFERENCES approval_records(approval_id) ON DELETE RESTRICT,
    CHECK (length(approval_envelope_digest) = 64),
    CHECK (length(authorization_source_digest) = 64),
    CHECK (length(effect_idempotency_key) > 0),
    CHECK (
        (status = 'started' AND receipt_id IS NULL AND outputs_hash IS NULL
            AND error_code IS NULL AND completed_at IS NULL)
        OR
        (status = 'uncertain' AND receipt_id IS NULL AND outputs_hash IS NULL
            AND length(error_code) > 0 AND completed_at IS NULL)
        OR
        (status = 'succeeded' AND length(receipt_id) > 0
            AND length(outputs_hash) = 64 AND error_code IS NULL
            AND completed_at IS NOT NULL)
    ),
    UNIQUE (tenant_id, workflow_id, effect_idempotency_key),
    UNIQUE (approval_id)
);

CREATE INDEX IF NOT EXISTS idx_approval_effect_executions_action
    ON approval_effect_executions(tenant_id, workflow_id, action_id, started_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_effect_executions_receipt
    ON approval_effect_executions(tenant_id, receipt_id)
    WHERE receipt_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS approval_effect_executions_identity_immutable
BEFORE UPDATE ON approval_effect_executions
WHEN NEW.execution_id IS NOT OLD.execution_id
    OR NEW.tenant_id IS NOT OLD.tenant_id
    OR NEW.workflow_id IS NOT OLD.workflow_id
    OR NEW.action_id IS NOT OLD.action_id
    OR NEW.approval_id IS NOT OLD.approval_id
    OR NEW.approval_envelope_digest IS NOT OLD.approval_envelope_digest
    OR NEW.authorization_source_digest IS NOT OLD.authorization_source_digest
    OR NEW.effect_idempotency_key IS NOT OLD.effect_idempotency_key
    OR NEW.started_at IS NOT OLD.started_at
BEGIN
    SELECT RAISE(ABORT, 'approval effect execution identity is immutable');
END;

CREATE TRIGGER IF NOT EXISTS approval_effect_executions_monotonic
BEFORE UPDATE ON approval_effect_executions
WHEN NOT (
    (OLD.status = 'started' AND NEW.status IN ('uncertain', 'succeeded'))
    OR (OLD.status = 'uncertain' AND NEW.status = 'succeeded')
)
BEGIN
    SELECT RAISE(ABORT, 'approval effect execution transition is invalid');
END;

CREATE TRIGGER IF NOT EXISTS approval_effect_executions_no_delete
BEFORE DELETE ON approval_effect_executions
BEGIN
    SELECT RAISE(ABORT, 'approval effect executions cannot be deleted');
END;
