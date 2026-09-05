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
WHEN NEW.scope_status != 'validated'
    OR NEW.source_metric_id IS NULL
    OR NEW.source_metric_id IS NOT json_extract(
        NEW.outputs_json, '$.source_metric_id'
    )
    OR NOT EXISTS (
        SELECT 1
        FROM experiments experiment
        JOIN experiment_variants variant
          ON variant.id = json_extract(NEW.outputs_json, '$.variant_id')
         AND variant.experiment_id = experiment.id
        JOIN experiment_metrics metric
          ON metric.id = NEW.source_metric_id
         AND metric.experiment_id = experiment.id
         AND metric.variant_id = variant.id
        WHERE experiment.id = json_extract(NEW.outputs_json, '$.experiment_id')
          AND experiment.client_id = NEW.tenant_id
    )
BEGIN
    SELECT RAISE(ABORT, 'governed effect receipt scope is invalid');
END;

CREATE TRIGGER governed_effect_receipts_immutable
BEFORE UPDATE ON governed_effect_receipts
BEGIN
    SELECT RAISE(ABORT, 'governed effect receipts are immutable');
END;
