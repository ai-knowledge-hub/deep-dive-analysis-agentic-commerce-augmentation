ALTER TABLE approval_effect_executions
    ADD COLUMN authorization_snapshot_json TEXT CHECK (
        authorization_snapshot_json IS NULL
        OR json_valid(authorization_snapshot_json)
    );
ALTER TABLE approval_effect_executions
    ADD COLUMN authorization_snapshot_digest TEXT CHECK (
        authorization_snapshot_digest IS NULL
        OR length(authorization_snapshot_digest) = 64
    );

ALTER TABLE validation_jobs
    ADD COLUMN agent_action_id TEXT REFERENCES agent_actions(id) ON DELETE RESTRICT;
ALTER TABLE validation_jobs
    ADD COLUMN approval_id TEXT REFERENCES approval_records(approval_id) ON DELETE RESTRICT;
ALTER TABLE validation_jobs
    ADD COLUMN effect_idempotency_key TEXT;
ALTER TABLE validation_jobs
    ADD COLUMN approval_effect_execution_id TEXT
        REFERENCES approval_effect_executions(execution_id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_validation_jobs_effect_execution
    ON validation_jobs(approval_effect_execution_id)
    WHERE approval_effect_execution_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS approval_effect_snapshot_required_for_new_start
BEFORE INSERT ON approval_effect_executions
WHEN NEW.authorization_snapshot_json IS NULL
    OR NEW.authorization_snapshot_digest IS NULL
BEGIN
    SELECT RAISE(ABORT, 'new approval effect starts require an authority snapshot');
END;

CREATE TRIGGER IF NOT EXISTS approval_effect_snapshot_immutable
BEFORE UPDATE ON approval_effect_executions
WHEN NEW.authorization_snapshot_json IS NOT OLD.authorization_snapshot_json
    OR NEW.authorization_snapshot_digest IS NOT OLD.authorization_snapshot_digest
BEGIN
    SELECT RAISE(ABORT, 'approval effect authorization snapshot is immutable');
END;

CREATE TRIGGER IF NOT EXISTS validation_job_effect_provenance_complete
BEFORE INSERT ON validation_jobs
WHEN (NEW.agent_action_id IS NOT NULL
        OR NEW.approval_id IS NOT NULL
        OR NEW.effect_idempotency_key IS NOT NULL
        OR NEW.approval_effect_execution_id IS NOT NULL)
    AND (NEW.agent_action_id IS NULL
        OR NEW.approval_id IS NULL
        OR NEW.effect_idempotency_key IS NULL
        OR NEW.approval_effect_execution_id IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'validation job effect provenance must be complete');
END;

CREATE TRIGGER IF NOT EXISTS validation_job_effect_provenance_matches_start
BEFORE INSERT ON validation_jobs
WHEN NEW.approval_effect_execution_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM approval_effect_executions effect
        WHERE effect.execution_id = NEW.approval_effect_execution_id
          AND effect.tenant_id = NEW.client_id
          AND effect.action_id = NEW.agent_action_id
          AND effect.approval_id = NEW.approval_id
          AND effect.effect_idempotency_key = NEW.effect_idempotency_key
    )
BEGIN
    SELECT RAISE(ABORT, 'validation job provenance does not match effect start');
END;

CREATE TRIGGER IF NOT EXISTS validation_job_effect_provenance_immutable
BEFORE UPDATE ON validation_jobs
WHEN NEW.agent_action_id IS NOT OLD.agent_action_id
    OR NEW.approval_id IS NOT OLD.approval_id
    OR NEW.effect_idempotency_key IS NOT OLD.effect_idempotency_key
    OR NEW.approval_effect_execution_id IS NOT OLD.approval_effect_execution_id
BEGIN
    SELECT RAISE(ABORT, 'validation job effect provenance is immutable');
END;
