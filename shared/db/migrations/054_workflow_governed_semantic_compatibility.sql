-- Slice 7b: immutable governed-semantic artifacts for the sequential-runtime
-- compatibility shadow. These rows are evidence of parity only; the approval,
-- effect, outcome, and completion ledgers remain authoritative.

CREATE VIEW IF NOT EXISTS workflow_compatibility_semantic_source_payloads AS
SELECT
    event.tenant_id,
    event.workflow_id,
    CAST(json_extract(event.envelope_json, '$.scope.active_graph_revision') AS INTEGER)
        AS graph_revision,
    'approval_event' AS artifact_type,
    event.event_id AS source_id,
    event.action_id AS task_id,
    NULL AS attempt_id,
    event.occurred_at AS recorded_at,
    json_object(
        'action_id', event.action_id,
        'approval_id', event.approval_id,
        'authority_source', event.authority_source,
        'authority_version', event.authority_version,
        'command_id', event.command_id,
        'envelope', json(event.envelope_json),
        'envelope_digest', event.envelope_digest,
        'event_index', event.event_index,
        'event_type', event.event_type,
        'principal_id', event.principal_id,
        'principal_type', event.principal_type,
        'sequence', event.sequence,
        'status', event.status
    ) AS payload_json
FROM approval_events event

UNION ALL

SELECT
    result.tenant_id,
    result.workflow_id,
    result.graph_revision,
    'accepted_result',
    result.result_id,
    result.task_id,
    result.attempt_id,
    result.validated_at,
    json_object(
        'assignment_id', result.assignment_id,
        'attempt_id', result.attempt_id,
        'command_id', result.command_id,
        'created_at', result.created_at,
        'payload', json(result.payload_json),
        'result_digest', result.result_digest,
        'result_id', result.result_id,
        'task_id', result.task_id,
        'validated_at', result.validated_at,
        'validation_status', result.validation_status
    )
FROM workflow_task_results result
WHERE result.validation_status = 'accepted'

UNION ALL

SELECT DISTINCT
    evidence.tenant_id,
    evidence.workflow_id,
    evidence.graph_revision,
    'evidence_record',
    evidence.evidence_id,
    evidence.task_id,
    evidence.attempt_id,
    evidence.recorded_at,
    json_object(
        'action_id', evidence.action_id,
        'attempt_id', evidence.attempt_id,
        'command_id', evidence.command_id,
        'evidence_digest', evidence.evidence_digest,
        'evidence_id', evidence.evidence_id,
        'payload', json(evidence.payload_json),
        'recorded_at', evidence.recorded_at,
        'task_id', evidence.task_id
    )
FROM workflow_evidence_records evidence
WHERE EXISTS (
    SELECT 1
    FROM workflow_result_evidence binding
    JOIN workflow_task_results result ON result.result_id = binding.result_id
    WHERE binding.evidence_id = evidence.evidence_id
      AND binding.evidence_digest = evidence.evidence_digest
      AND result.validation_status = 'accepted'
)
OR EXISTS (
    SELECT 1
    FROM workflow_completion_decision_evidence binding
    WHERE binding.evidence_id = evidence.evidence_id
      AND binding.evidence_digest = evidence.evidence_digest
)

UNION ALL

SELECT
    result.tenant_id,
    result.workflow_id,
    result.graph_revision,
    'result_evidence_binding',
    binding.result_id || ':' || binding.evidence_id,
    result.task_id,
    result.attempt_id,
    evidence.recorded_at,
    json_object(
        'evidence_digest', binding.evidence_digest,
        'evidence_id', binding.evidence_id,
        'result_digest', result.result_digest,
        'result_id', binding.result_id
    )
FROM workflow_result_evidence binding
JOIN workflow_task_results result ON result.result_id = binding.result_id
JOIN workflow_evidence_records evidence
  ON evidence.evidence_id = binding.evidence_id
 AND evidence.evidence_digest = binding.evidence_digest
WHERE result.validation_status = 'accepted'

UNION ALL

SELECT
    effect.tenant_id,
    effect.workflow_id,
    CAST(json_extract(
        effect.authorization_snapshot_json,
        '$.approval_envelope.scope.active_graph_revision'
    ) AS INTEGER),
    'effect_receipt',
    effect.execution_id,
    effect.action_id,
    NULL,
    effect.completed_at,
    json_object(
        'action_id', effect.action_id,
        'approval_envelope_digest', effect.approval_envelope_digest,
        'approval_id', effect.approval_id,
        'authorization_snapshot_digest', effect.authorization_snapshot_digest,
        'authorization_source_digest', effect.authorization_source_digest,
        'completed_at', effect.completed_at,
        'effect_idempotency_key', effect.effect_idempotency_key,
        'execution_id', effect.execution_id,
        'outputs_hash', effect.outputs_hash,
        'receipt_id', effect.receipt_id,
        'started_at', effect.started_at,
        'status', effect.status
    )
FROM approval_effect_executions effect
WHERE effect.status = 'succeeded'

UNION ALL

SELECT
    effect.tenant_id,
    effect.workflow_id,
    CAST(json_extract(
        effect.authorization_snapshot_json,
        '$.approval_envelope.scope.active_graph_revision'
    ) AS INTEGER),
    'validation_job_receipt',
    job.id,
    effect.action_id,
    NULL,
    job.created_at,
    json_object(
        'agent_action_id', job.agent_action_id,
        'approval_effect_execution_id', job.approval_effect_execution_id,
        'approval_id', job.approval_id,
        'effect_idempotency_key', job.effect_idempotency_key,
        'entity_id', job.entity_id,
        'entity_type', job.entity_type,
        'input_payload', json(job.input_payload_json),
        'job_id', job.id,
        'mode', job.mode,
        'prompt_version', job.prompt_version,
        'provider', job.provider,
        'requested_model', job.requested_model
    )
FROM validation_jobs job
JOIN approval_effect_executions effect
  ON effect.execution_id = job.approval_effect_execution_id
WHERE effect.status = 'succeeded'

UNION ALL

SELECT
    effect.tenant_id,
    effect.workflow_id,
    CAST(json_extract(
        effect.authorization_snapshot_json,
        '$.approval_envelope.scope.active_graph_revision'
    ) AS INTEGER),
    'validation_result_receipt',
    result.id,
    effect.action_id,
    NULL,
    result.created_at,
    json_object(
        'cost_usd', result.cost_usd,
        'evidence_strength', result.evidence_strength,
        'job_id', result.job_id,
        'latency_ms', result.latency_ms,
        'model', result.model,
        'provider', result.provider,
        'raw_response_hash', workflow_sha256(COALESCE(result.raw_response_text, '')),
        'result_id', result.id,
        'score', result.score,
        'structured_result', json(result.structured_result_json),
        'winner_id', result.winner_id
    )
FROM validation_results result
JOIN validation_jobs job ON job.id = result.job_id
JOIN approval_effect_executions effect
  ON effect.execution_id = job.approval_effect_execution_id
WHERE effect.status = 'succeeded'

UNION ALL

SELECT
    receipt.tenant_id,
    receipt.workflow_id,
    CAST(json_extract(
        effect.authorization_snapshot_json,
        '$.approval_envelope.scope.active_graph_revision'
    ) AS INTEGER),
    'governed_effect_receipt',
    receipt.receipt_id,
    receipt.action_id,
    NULL,
    receipt.created_at,
    json_object(
        'analytics_event_id', receipt.analytics_event_id,
        'approval_effect_execution_id', receipt.approval_effect_execution_id,
        'approval_id', receipt.approval_id,
        'capability_name', receipt.capability_name,
        'decision_event_id', receipt.decision_event_id,
        'effect_idempotency_key', receipt.effect_idempotency_key,
        'outputs', json(receipt.outputs_json),
        'outputs_hash', receipt.outputs_hash,
        'receipt_id', receipt.receipt_id,
        'scope_status', receipt.scope_status,
        'source_metric_id', receipt.source_metric_id
    )
FROM governed_effect_receipts receipt
JOIN approval_effect_executions effect
  ON effect.execution_id = receipt.approval_effect_execution_id

UNION ALL

SELECT
    criteria.tenant_id,
    criteria.workflow_id,
    criteria.graph_revision,
    'completion_criteria',
    criteria.criteria_digest,
    NULL,
    NULL,
    criteria.created_at,
    json_object(
        'authority_hash', criteria.authority_hash,
        'command_id', criteria.command_id,
        'criteria_digest', criteria.criteria_digest,
        'criteria_id', criteria.criteria_id,
        'criteria_version', criteria.criteria_version,
        'objective_id', criteria.objective_id,
        'payload', json(criteria.payload_json)
    )
FROM workflow_completion_criteria criteria

UNION ALL

SELECT
    criteria.tenant_id,
    criteria.workflow_id,
    criteria.graph_revision,
    'completion_task_definition',
    definition.criteria_digest || ':' || definition.task_id,
    definition.task_id,
    NULL,
    criteria.created_at,
    json_object(
        'criteria_digest', definition.criteria_digest,
        'result_schema_hash', definition.result_schema_hash,
        'result_schema_id', definition.result_schema_id,
        'result_schema_version', definition.result_schema_version,
        'task_id', definition.task_id,
        'task_input_hash', definition.task_input_hash
    )
FROM workflow_completion_task_definitions definition
JOIN workflow_completion_criteria criteria
  ON criteria.criteria_digest = definition.criteria_digest

UNION ALL

SELECT
    snapshot.tenant_id,
    snapshot.workflow_id,
    snapshot.graph_revision,
    'completion_authority_snapshot',
    snapshot.snapshot_id,
    NULL,
    NULL,
    snapshot.issued_at,
    json_object(
        'command_id', snapshot.command_id,
        'criteria_digest', snapshot.criteria_digest,
        'criteria_id', snapshot.criteria_id,
        'objective_id', snapshot.objective_id,
        'payload', json(snapshot.payload_json),
        'snapshot_digest', snapshot.snapshot_digest,
        'snapshot_id', snapshot.snapshot_id
    )
FROM workflow_completion_authority_snapshots snapshot

UNION ALL

SELECT
    snapshot.tenant_id,
    snapshot.workflow_id,
    snapshot.graph_revision,
    'snapshot_result_binding',
    binding.snapshot_id || ':' || binding.task_id,
    binding.task_id,
    result.attempt_id,
    snapshot.issued_at,
    json_object(
        'result_digest', binding.result_digest,
        'result_id', binding.result_id,
        'snapshot_digest', snapshot.snapshot_digest,
        'snapshot_id', binding.snapshot_id,
        'task_id', binding.task_id
    )
FROM workflow_completion_snapshot_results binding
JOIN workflow_completion_authority_snapshots snapshot
  ON snapshot.snapshot_id = binding.snapshot_id
JOIN workflow_task_results result
  ON result.result_id = binding.result_id
 AND result.result_digest = binding.result_digest

UNION ALL

SELECT
    decision.tenant_id,
    decision.workflow_id,
    decision.graph_revision,
    'completion_decision',
    decision.decision_id,
    NULL,
    NULL,
    decision.evaluated_at,
    json_object(
        'authoritative_event_sequence', decision.authoritative_event_sequence,
        'command_id', decision.command_id,
        'criteria_digest', decision.criteria_digest,
        'criteria_id', decision.criteria_id,
        'decision_digest', decision.decision_digest,
        'decision_id', decision.decision_id,
        'evaluated_at', decision.evaluated_at,
        'objective_id', decision.objective_id,
        'payload', json(decision.payload_json),
        'snapshot_digest', decision.snapshot_digest,
        'snapshot_id', decision.snapshot_id,
        'status', decision.status
    )
FROM workflow_completion_decisions decision

UNION ALL

SELECT
    decision.tenant_id,
    decision.workflow_id,
    decision.graph_revision,
    'decision_result_binding',
    binding.decision_id || ':' || binding.result_id,
    result.task_id,
    result.attempt_id,
    decision.evaluated_at,
    json_object(
        'decision_digest', decision.decision_digest,
        'decision_id', binding.decision_id,
        'result_digest', binding.result_digest,
        'result_id', binding.result_id
    )
FROM workflow_completion_decision_results binding
JOIN workflow_completion_decisions decision
  ON decision.decision_id = binding.decision_id
JOIN workflow_task_results result
  ON result.result_id = binding.result_id
 AND result.result_digest = binding.result_digest

UNION ALL

SELECT
    decision.tenant_id,
    decision.workflow_id,
    decision.graph_revision,
    'decision_evidence_binding',
    binding.decision_id || ':' || binding.evidence_id,
    evidence.task_id,
    evidence.attempt_id,
    decision.evaluated_at,
    json_object(
        'decision_digest', decision.decision_digest,
        'decision_id', binding.decision_id,
        'evidence_digest', binding.evidence_digest,
        'evidence_id', binding.evidence_id
    )
FROM workflow_completion_decision_evidence binding
JOIN workflow_completion_decisions decision
  ON decision.decision_id = binding.decision_id
JOIN workflow_evidence_records evidence
  ON evidence.evidence_id = binding.evidence_id
 AND evidence.evidence_digest = binding.evidence_digest

UNION ALL

SELECT
    lifecycle.tenant_id,
    lifecycle.workflow_id,
    lifecycle.graph_revision,
    'completion_checkpoint',
    lifecycle.event_id,
    NULL,
    NULL,
    lifecycle.created_at,
    json_object(
        'action_projection_digest', lifecycle.action_projection_digest,
        'authoritative_event_sequence', lifecycle.authoritative_event_sequence,
        'command_id', lifecycle.command_id,
        'completion_status', lifecycle.completion_status,
        'decision_digest', lifecycle.decision_digest,
        'decision_id', lifecycle.decision_id,
        'event_id', lifecycle.event_id,
        'payload', json(lifecycle.payload_json),
        'prior_run_state', lifecycle.prior_run_state,
        'prior_run_status', lifecycle.prior_run_status,
        'projected_run_state', lifecycle.projected_run_state,
        'projected_run_status', lifecycle.projected_run_status
    )
FROM workflow_completion_lifecycle_events lifecycle;

CREATE VIEW IF NOT EXISTS workflow_compatibility_semantic_sources AS
SELECT
    tenant_id,
    workflow_id,
    graph_revision,
    artifact_type,
    source_id,
    task_id,
    attempt_id,
    payload_json,
    workflow_sha256(payload_json) AS payload_hash,
    recorded_at
FROM workflow_compatibility_semantic_source_payloads;

CREATE TABLE IF NOT EXISTS workflow_compatibility_semantic_artifacts (
    semantic_artifact_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    artifact_type TEXT NOT NULL CHECK (artifact_type IN (
        'approval_event',
        'accepted_result',
        'evidence_record',
        'result_evidence_binding',
        'effect_receipt',
        'validation_job_receipt',
        'validation_result_receipt',
        'governed_effect_receipt',
        'completion_criteria',
        'completion_task_definition',
        'completion_authority_snapshot',
        'snapshot_result_binding',
        'completion_decision',
        'decision_result_binding',
        'decision_evidence_binding',
        'completion_checkpoint'
    )),
    source_id TEXT NOT NULL,
    task_id TEXT,
    attempt_id TEXT,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    payload_hash TEXT NOT NULL CHECK (length(payload_hash) = 64),
    source_recorded_at TEXT NOT NULL,
    projected_at TEXT NOT NULL,
    UNIQUE (tenant_id, workflow_id, artifact_type, source_id),
    FOREIGN KEY (tenant_id, workflow_id, graph_revision)
        REFERENCES workflow_compatibility_revisions(
            tenant_id, workflow_id, revision
        ) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id, task_id)
        REFERENCES workflow_compatibility_tasks(
            tenant_id, workflow_id, task_id
        ) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_semantic_no_replace
BEFORE INSERT ON workflow_compatibility_semantic_artifacts
WHEN EXISTS (
    SELECT 1 FROM workflow_compatibility_semantic_artifacts stored
    WHERE stored.semantic_artifact_id = NEW.semantic_artifact_id
       OR (
         stored.tenant_id = NEW.tenant_id
         AND stored.workflow_id = NEW.workflow_id
         AND stored.artifact_type = NEW.artifact_type
         AND stored.source_id = NEW.source_id
       )
)
BEGIN
    SELECT RAISE(ABORT, 'workflow semantic artifact already exists');
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_semantic_source_guard
BEFORE INSERT ON workflow_compatibility_semantic_artifacts
BEGIN
    SELECT CASE WHEN NEW.semantic_artifact_id <>
        'workflow-semantic:' || NEW.artifact_type || ':' || NEW.source_id
      OR NOT EXISTS (
        SELECT 1
        FROM workflow_compatibility_semantic_sources source
        WHERE source.tenant_id = NEW.tenant_id
          AND source.workflow_id = NEW.workflow_id
          AND source.graph_revision = NEW.graph_revision
          AND source.artifact_type = NEW.artifact_type
          AND source.source_id = NEW.source_id
          AND source.task_id IS NEW.task_id
          AND source.attempt_id IS NEW.attempt_id
          AND source.payload_json = NEW.payload_json
          AND source.payload_hash = NEW.payload_hash
          AND source.recorded_at = NEW.source_recorded_at
      )
    THEN RAISE(ABORT, 'workflow semantic source artifact is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_semantic_no_update
BEFORE UPDATE ON workflow_compatibility_semantic_artifacts
BEGIN SELECT RAISE(ABORT, 'workflow semantic artifacts are immutable'); END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_semantic_no_delete
BEFORE DELETE ON workflow_compatibility_semantic_artifacts
BEGIN SELECT RAISE(ABORT, 'workflow semantic artifacts are immutable'); END;

CREATE TABLE IF NOT EXISTS workflow_compatibility_semantic_status (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    parity_state TEXT NOT NULL CHECK (
        parity_state IN ('current', 'drifted', 'not_governed', 'failed')
    ),
    source_artifact_count INTEGER NOT NULL CHECK (source_artifact_count >= 0),
    projected_artifact_count INTEGER NOT NULL CHECK (projected_artifact_count >= 0),
    completion_decision_id TEXT,
    completion_decision_digest TEXT,
    completion_event_sequence INTEGER,
    completion_projection_version INTEGER,
    completion_projection_hash TEXT,
    error_code TEXT,
    checked_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES workflow_compatibility_runs(tenant_id, workflow_id)
        ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_semantic_status_scope_insert
BEFORE INSERT ON workflow_compatibility_semantic_status
WHEN NOT EXISTS (
    SELECT 1 FROM workflow_compatibility_runs shadow
    WHERE shadow.tenant_id = NEW.tenant_id
      AND shadow.workflow_id = NEW.workflow_id
)
BEGIN SELECT RAISE(ABORT, 'workflow semantic status scope is invalid'); END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_semantic_status_scope_update
BEFORE UPDATE ON workflow_compatibility_semantic_status
WHEN NEW.tenant_id <> OLD.tenant_id OR NEW.workflow_id <> OLD.workflow_id
BEGIN SELECT RAISE(ABORT, 'workflow semantic status scope is immutable'); END;
