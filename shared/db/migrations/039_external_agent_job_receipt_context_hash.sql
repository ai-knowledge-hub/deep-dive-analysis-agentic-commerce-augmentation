ALTER TABLE external_agent_job_receipts
ADD COLUMN receipt_context_hash TEXT NOT NULL DEFAULT '';

UPDATE external_agent_job_receipts
SET receipt_context_hash = COALESCE(
    json_extract(payload_json, '$.receipt_context_hash'),
    status
)
WHERE receipt_context_hash = '';

DROP INDEX IF EXISTS ux_external_agent_job_receipts_job_status;

CREATE UNIQUE INDEX IF NOT EXISTS ux_external_agent_job_receipts_job_status_context
ON external_agent_job_receipts(job_id, status, receipt_context_hash);
