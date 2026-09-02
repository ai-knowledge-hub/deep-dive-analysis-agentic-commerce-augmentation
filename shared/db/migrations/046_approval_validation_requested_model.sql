ALTER TABLE validation_jobs
    ADD COLUMN requested_model TEXT;

UPDATE validation_jobs
SET requested_model = CASE
    WHEN approval_effect_execution_id IS NULL THEN model
    ELSE (
        SELECT json_extract(
            effect.authorization_snapshot_json,
            '$.executable_inputs.model'
        )
        FROM approval_effect_executions effect
        WHERE effect.execution_id = validation_jobs.approval_effect_execution_id
    )
END;

DROP TRIGGER IF EXISTS validation_job_effect_provenance_matches_start;
CREATE TRIGGER validation_job_effect_provenance_matches_start
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
          AND NEW.requested_model IS json_extract(
              effect.authorization_snapshot_json,
              '$.executable_inputs.model'
          )
    )
BEGIN
    SELECT RAISE(ABORT, 'validation job provenance does not match effect start');
END;

DROP TRIGGER IF EXISTS validation_job_effect_provenance_immutable;
CREATE TRIGGER validation_job_effect_provenance_immutable
BEFORE UPDATE ON validation_jobs
WHEN NEW.agent_action_id IS NOT OLD.agent_action_id
    OR NEW.approval_id IS NOT OLD.approval_id
    OR NEW.effect_idempotency_key IS NOT OLD.effect_idempotency_key
    OR NEW.approval_effect_execution_id IS NOT OLD.approval_effect_execution_id
    OR NEW.requested_model IS NOT OLD.requested_model
BEGIN
    SELECT RAISE(ABORT, 'validation job effect provenance and requested model are immutable');
END;
