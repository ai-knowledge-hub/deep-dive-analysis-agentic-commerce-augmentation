CREATE TABLE IF NOT EXISTS governed_effect_receipts (
    receipt_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    effect_idempotency_key TEXT NOT NULL,
    approval_effect_execution_id TEXT NOT NULL UNIQUE,
    capability_name TEXT NOT NULL,
    analytics_event_id TEXT NOT NULL UNIQUE,
    decision_event_id TEXT NOT NULL UNIQUE,
    outputs_json TEXT NOT NULL CHECK (json_valid(outputs_json)),
    outputs_hash TEXT NOT NULL CHECK (length(outputs_hash) = 64),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tenant_id) REFERENCES clients(id) ON DELETE RESTRICT,
    FOREIGN KEY (workflow_id) REFERENCES agent_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id) ON DELETE RESTRICT,
    FOREIGN KEY (approval_id) REFERENCES approval_records(approval_id) ON DELETE RESTRICT,
    FOREIGN KEY (approval_effect_execution_id)
        REFERENCES approval_effect_executions(execution_id) ON DELETE RESTRICT,
    FOREIGN KEY (analytics_event_id) REFERENCES analytics_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (decision_event_id) REFERENCES decision_events(id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, effect_idempotency_key),
    CHECK (capability_name = 'promote_variant_lab')
);

CREATE INDEX IF NOT EXISTS idx_governed_effect_receipts_action
    ON governed_effect_receipts(tenant_id, workflow_id, action_id, created_at DESC);

CREATE TRIGGER IF NOT EXISTS governed_effect_receipt_matches_start
BEFORE INSERT ON governed_effect_receipts
WHEN NOT EXISTS (
    SELECT 1
    FROM approval_effect_executions effect
    WHERE effect.execution_id = NEW.approval_effect_execution_id
      AND effect.tenant_id = NEW.tenant_id
      AND effect.workflow_id = NEW.workflow_id
      AND effect.action_id = NEW.action_id
      AND effect.approval_id = NEW.approval_id
      AND effect.effect_idempotency_key = NEW.effect_idempotency_key
      AND effect.status IN ('started', 'uncertain')
)
BEGIN
    SELECT RAISE(ABORT, 'governed effect receipt does not match effect start');
END;

CREATE TRIGGER IF NOT EXISTS governed_effect_receipts_immutable
BEFORE UPDATE ON governed_effect_receipts
BEGIN
    SELECT RAISE(ABORT, 'governed effect receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS governed_effect_receipts_no_delete
BEFORE DELETE ON governed_effect_receipts
BEGIN
    SELECT RAISE(ABORT, 'governed effect receipts cannot be deleted');
END;
