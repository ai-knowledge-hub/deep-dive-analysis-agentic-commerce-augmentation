DROP TRIGGER IF EXISTS governed_effect_receipts_immutable;

ALTER TABLE governed_effect_receipts
    ADD COLUMN source_metric_id TEXT
        REFERENCES experiment_metrics(id) ON DELETE RESTRICT;
ALTER TABLE governed_effect_receipts
    ADD COLUMN scope_status TEXT NOT NULL DEFAULT 'unverified_legacy'
        CHECK (scope_status IN ('validated', 'invalid_legacy', 'unverified_legacy'));

UPDATE governed_effect_receipts
SET source_metric_id = CASE
    WHEN EXISTS (
        SELECT 1
        FROM experiment_metrics metric
        WHERE metric.id = json_extract(
            governed_effect_receipts.outputs_json, '$.source_metric_id'
        )
    ) THEN json_extract(outputs_json, '$.source_metric_id')
    ELSE NULL
END;

UPDATE governed_effect_receipts
SET scope_status = CASE
    WHEN EXISTS (
        SELECT 1
        FROM experiments experiment
        JOIN experiment_variants variant
          ON variant.id = json_extract(
              governed_effect_receipts.outputs_json, '$.variant_id'
          )
         AND variant.experiment_id = experiment.id
        JOIN experiment_metrics metric
          ON metric.id = governed_effect_receipts.source_metric_id
         AND metric.experiment_id = experiment.id
         AND metric.variant_id = variant.id
        WHERE experiment.id = json_extract(
                  governed_effect_receipts.outputs_json, '$.experiment_id'
              )
          AND experiment.client_id = governed_effect_receipts.tenant_id
    ) THEN 'validated'
    ELSE 'invalid_legacy'
END;

CREATE INDEX IF NOT EXISTS idx_governed_effect_receipts_metric
    ON governed_effect_receipts(source_metric_id);

CREATE TRIGGER governed_effect_receipt_validated_scope
BEFORE INSERT ON governed_effect_receipts
WHEN (
        NOT (
            NEW.scope_status = 'validated'
            AND NEW.source_metric_id IS NOT NULL
            AND NEW.source_metric_id IS json_extract(
                NEW.outputs_json, '$.source_metric_id'
            )
        )
        AND NOT (
            NEW.scope_status = 'unverified_legacy'
            AND NEW.source_metric_id IS NULL
            AND json_type(NEW.outputs_json, '$.source_metric_id') = 'text'
        )
    )
    OR NOT EXISTS (
        SELECT 1
        FROM experiments experiment
        JOIN experiment_variants variant
          ON variant.id = json_extract(NEW.outputs_json, '$.variant_id')
         AND variant.experiment_id = experiment.id
        JOIN experiment_metrics metric
          ON metric.id = COALESCE(
              NEW.source_metric_id,
              json_extract(NEW.outputs_json, '$.source_metric_id')
          )
         AND metric.experiment_id = experiment.id
         AND metric.variant_id = variant.id
        WHERE experiment.id = json_extract(NEW.outputs_json, '$.experiment_id')
          AND experiment.client_id = NEW.tenant_id
    )
BEGIN
    SELECT RAISE(ABORT, 'governed effect receipt scope is invalid');
END;

CREATE TRIGGER governed_effect_receipt_previous_writer_compatibility
AFTER INSERT ON governed_effect_receipts
WHEN NEW.scope_status = 'unverified_legacy'
    AND NEW.source_metric_id IS NULL
BEGIN
    UPDATE governed_effect_receipts
    SET source_metric_id = json_extract(NEW.outputs_json, '$.source_metric_id'),
        scope_status = 'validated'
    WHERE receipt_id = NEW.receipt_id;
END;

CREATE TRIGGER governed_effect_receipts_immutable
BEFORE UPDATE ON governed_effect_receipts
WHEN NOT (
        OLD.scope_status = 'unverified_legacy'
        AND OLD.source_metric_id IS NULL
        AND NEW.scope_status = 'validated'
        AND NEW.source_metric_id IS json_extract(
            OLD.outputs_json, '$.source_metric_id'
        )
        AND NEW.receipt_id IS OLD.receipt_id
        AND NEW.tenant_id IS OLD.tenant_id
        AND NEW.workflow_id IS OLD.workflow_id
        AND NEW.action_id IS OLD.action_id
        AND NEW.approval_id IS OLD.approval_id
        AND NEW.effect_idempotency_key IS OLD.effect_idempotency_key
        AND NEW.approval_effect_execution_id
            IS OLD.approval_effect_execution_id
        AND NEW.capability_name IS OLD.capability_name
        AND NEW.analytics_event_id IS OLD.analytics_event_id
        AND NEW.decision_event_id IS OLD.decision_event_id
        AND NEW.outputs_json IS OLD.outputs_json
        AND NEW.outputs_hash IS OLD.outputs_hash
        AND NEW.created_at IS OLD.created_at
    )
    OR NOT EXISTS (
        SELECT 1
        FROM experiments experiment
        JOIN experiment_variants variant
          ON variant.id = json_extract(OLD.outputs_json, '$.variant_id')
         AND variant.experiment_id = experiment.id
        JOIN experiment_metrics metric
          ON metric.id = NEW.source_metric_id
         AND metric.experiment_id = experiment.id
         AND metric.variant_id = variant.id
        WHERE experiment.id = json_extract(OLD.outputs_json, '$.experiment_id')
          AND experiment.client_id = NEW.tenant_id
    )
BEGIN
    SELECT RAISE(ABORT, 'governed effect receipts are immutable');
END;
