-- Phase 2.5a: exact same-action retries with independent recovery receipts.

CREATE TABLE IF NOT EXISTS operator_retry_proposals (
    proposal_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    command_type TEXT NOT NULL CHECK (command_type = 'retry'),
    proposal_digest TEXT NOT NULL CHECK (length(proposal_digest) = 64),
    proposal_json TEXT NOT NULL CHECK (json_valid(proposal_json)),
    active_graph_revision INTEGER NOT NULL CHECK (active_graph_revision >= 1),
    source_run_status TEXT NOT NULL CHECK (source_run_status IN ('planned', 'running', 'paused')),
    source_run_mode TEXT GENERATED ALWAYS AS (json_extract(proposal_json, '$.source.run_mode')) VIRTUAL NOT NULL CHECK (source_run_mode IN ('plan_only', 'auto_execute_safe')),
    source_run_state TEXT NOT NULL,
    snapshot_digest TEXT NOT NULL CHECK (length(snapshot_digest) = 64),
    snapshot_cursor TEXT,
    latest_event_id TEXT,
    latest_event_timestamp TEXT,
    harness_id TEXT,
    policy_profile_id TEXT,
    registry_version TEXT,
    registry_fingerprint TEXT,
    preflight_digest TEXT NOT NULL CHECK (length(preflight_digest) = 64),
    idempotency_key TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    action_id TEXT GENERATED ALWAYS AS (json_extract(proposal_json, '$.parameters.action_id')) VIRTUAL NOT NULL REFERENCES agent_actions(id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (principal_id) REFERENCES principals(id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key),
    CHECK (
        (latest_event_id IS NULL AND latest_event_timestamp IS NULL)
        OR (latest_event_id IS NOT NULL AND latest_event_timestamp IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS operator_retry_receipts (
    receipt_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    command_type TEXT NOT NULL CHECK (command_type = 'retry'),
    proposal_digest TEXT NOT NULL CHECK (length(proposal_digest) = 64),
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    outcome TEXT NOT NULL CHECK (outcome = 'proposed'),
    prior_run_status TEXT NOT NULL CHECK (prior_run_status IN ('planned', 'running', 'paused')),
    run_mode TEXT GENERATED ALWAYS AS (json_extract(receipt_json, '$.run_mode')) VIRTUAL NOT NULL CHECK (run_mode IN ('plan_only', 'auto_execute_safe')),
    resulting_run_status TEXT NOT NULL CHECK (resulting_run_status = prior_run_status),
    resulting_run_state TEXT NOT NULL,
    active_graph_revision INTEGER NOT NULL CHECK (active_graph_revision >= 1),
    command_event_id TEXT NOT NULL,
    lifecycle_event_id TEXT NOT NULL,
    stopping_event_id TEXT CHECK (stopping_event_id IS NULL),
    acknowledgement TEXT NOT NULL CHECK (acknowledgement = 'retry_action_proposed'),
    propagation_state TEXT NOT NULL CHECK (
        propagation_state = 'runtime_propagation_not_certified'
    ),
    receipt_json TEXT NOT NULL CHECK (json_valid(receipt_json)),
    receipt_digest TEXT NOT NULL CHECK (length(receipt_digest) = 64),
    completed_at TEXT NOT NULL,
    action_id TEXT GENERATED ALWAYS AS (json_extract(receipt_json, '$.action_id')) VIRTUAL NOT NULL REFERENCES agent_actions(id) ON DELETE RESTRICT,
    FOREIGN KEY (proposal_id) REFERENCES operator_retry_proposals(proposal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (principal_id) REFERENCES principals(id) ON DELETE RESTRICT,
    FOREIGN KEY (command_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (lifecycle_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (stopping_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key),
    UNIQUE (action_id),
    CHECK (outcome = 'proposed')
);


CREATE TRIGGER operator_retry_proposal_scope
BEFORE INSERT ON operator_retry_proposals
BEGIN
 SELECT CASE WHEN NOT EXISTS (
  SELECT 1 FROM agent_runs run JOIN agent_actions action ON action.agent_run_id = run.id
  JOIN principals human ON human.id = NEW.principal_id
  WHERE run.id = NEW.workflow_id AND run.client_id = NEW.tenant_id
   AND run.status = NEW.source_run_status AND run.state = NEW.source_run_state
   AND run.active_graph_revision = NEW.active_graph_revision AND run.lock_token IS NULL
   AND human.tenant_id = NEW.tenant_id AND human.principal_type = 'human' AND human.status = 'active'
   AND action.id = NEW.action_id AND action.status = 'failed'
   AND run.run_mode = NEW.source_run_mode
 ) THEN RAISE(ABORT, 'retry source changed') END;
 SELECT CASE WHEN json_extract(NEW.proposal_json, '$.contract') IS NOT 'workflow.operator-command-proposal.v5'
  OR json_extract(NEW.proposal_json, '$.proposal_id') IS NOT NEW.proposal_id
  OR json_extract(NEW.proposal_json, '$.tenant_id') IS NOT NEW.tenant_id
  OR json_extract(NEW.proposal_json, '$.run_id') IS NOT NEW.workflow_id
  OR json_extract(NEW.proposal_json, '$.principal_id') IS NOT NEW.principal_id
  OR json_extract(NEW.proposal_json, '$.command_type') IS NOT NEW.command_type
  OR json_extract(NEW.proposal_json, '$.proposal_digest') IS NOT NEW.proposal_digest
 THEN RAISE(ABORT, 'retry proposal identity changed') END;
END;

CREATE TRIGGER operator_retry_receipt_scope
BEFORE INSERT ON operator_retry_receipts
BEGIN
 SELECT CASE WHEN json_extract(NEW.receipt_json, '$.contract') IS NOT 'workflow.operator-command-receipt.v5'
  OR json_extract(NEW.receipt_json, '$.receipt_id') IS NOT NEW.receipt_id
  OR json_extract(NEW.receipt_json, '$.proposal_id') IS NOT NEW.proposal_id
  OR json_extract(NEW.receipt_json, '$.proposal_digest') IS NOT NEW.proposal_digest
  OR json_extract(NEW.receipt_json, '$.tenant_id') IS NOT NEW.tenant_id
  OR json_extract(NEW.receipt_json, '$.run_id') IS NOT NEW.workflow_id
  OR json_extract(NEW.receipt_json, '$.principal_id') IS NOT NEW.principal_id
  OR json_extract(NEW.receipt_json, '$.command_type') IS NOT NEW.command_type
  OR json_extract(NEW.receipt_json, '$.idempotency_key') IS NOT NEW.idempotency_key
  OR json_extract(NEW.receipt_json, '$.receipt_digest') IS NOT NEW.receipt_digest
 THEN RAISE(ABORT, 'retry receipt identity changed') END;
 SELECT CASE WHEN NOT EXISTS (
  SELECT 1 FROM operator_retry_proposals proposal
  JOIN agent_runs run ON run.id = NEW.workflow_id AND run.client_id = NEW.tenant_id
  JOIN agent_actions source ON source.id = proposal.action_id AND source.agent_run_id = run.id
  JOIN agent_actions child ON child.id = NEW.action_id AND child.agent_run_id = run.id
  JOIN agent_events audit ON audit.id = NEW.command_event_id
  JOIN agent_events lifecycle ON lifecycle.id = NEW.lifecycle_event_id
  WHERE proposal.proposal_id = NEW.proposal_id
   AND proposal.tenant_id = NEW.tenant_id AND proposal.workflow_id = NEW.workflow_id
   AND proposal.principal_id = NEW.principal_id AND proposal.proposal_digest = NEW.proposal_digest
   AND proposal.idempotency_key = NEW.idempotency_key
   AND source.status = 'failed' AND child.status = 'proposed' AND child.id <> source.id
   AND child.validation_job_id IS NULL AND child.approval_id IS NULL
   AND child.outputs_json = '{}' AND child.receipt_id IS NULL
   AND child.inputs_hash = json_extract(proposal.proposal_json, '$.parameters.retry_plan.inputs_hash')
   AND child.inputs_hash = json_extract(NEW.receipt_json, '$.inputs_hash')
   AND json_extract(NEW.receipt_json, '$.source_action_id') = source.id
   AND json_extract(NEW.receipt_json, '$.retry_strategy') = 'same_action'
   AND child.dedupe_key = 'retry:' || source.id || ':same_action:' || child.retry_count
   AND child.dedupe_key = json_extract(NEW.receipt_json, '$.effect_idempotency_key')
   AND child.retry_count = json_extract(NEW.receipt_json, '$.retry_count')
   AND child.sequence = json_extract(NEW.receipt_json, '$.action_sequence')
   AND run.status = NEW.resulting_run_status AND run.state = NEW.resulting_run_state
   AND run.active_graph_revision = NEW.active_graph_revision AND run.run_mode = NEW.run_mode
   AND audit.agent_run_id = run.id AND audit.action_id = child.id AND audit.principal_id = NEW.principal_id
   AND audit.principal_type = 'human' AND audit.event_type = 'operator_command_retry' AND audit.status = 'completed'
   AND json_extract(audit.anchors_json, '$.proposal_id') = NEW.proposal_id
   AND json_extract(audit.anchors_json, '$.receipt_id') = NEW.receipt_id
   AND lifecycle.agent_run_id = run.id AND lifecycle.action_id = child.id
   AND lifecycle.principal_id = NEW.principal_id AND lifecycle.principal_type = 'human'
   AND lifecycle.event_type = 'action_retry_proposed' AND lifecycle.status = 'proposed'
   AND json_extract(lifecycle.anchors_json, '$.proposal_id') = NEW.proposal_id
   AND json_extract(lifecycle.anchors_json, '$.receipt_id') = NEW.receipt_id
 ) THEN RAISE(ABORT, 'retry receipt has no exact proposed action') END;
END;

CREATE INDEX operator_retry_proposals_scope ON operator_retry_proposals(tenant_id, workflow_id, created_at, proposal_id);
CREATE INDEX operator_retry_receipts_scope ON operator_retry_receipts(tenant_id, workflow_id, completed_at, receipt_id);

CREATE TRIGGER operator_retry_proposals_no_update BEFORE UPDATE ON operator_retry_proposals BEGIN SELECT RAISE(ABORT, 'retry records are immutable'); END;

CREATE TRIGGER operator_retry_proposals_no_delete BEFORE DELETE ON operator_retry_proposals BEGIN SELECT RAISE(ABORT, 'retry records are immutable'); END;

CREATE TRIGGER operator_retry_proposals_no_replace BEFORE INSERT ON operator_retry_proposals WHEN EXISTS (SELECT 1 FROM operator_retry_proposals old WHERE old.proposal_id = NEW.proposal_id OR (old.tenant_id = NEW.tenant_id AND old.workflow_id = NEW.workflow_id AND old.idempotency_key = NEW.idempotency_key)) BEGIN SELECT RAISE(ABORT, 'retry identity already exists'); END;

CREATE TRIGGER operator_retry_receipts_no_update BEFORE UPDATE ON operator_retry_receipts BEGIN SELECT RAISE(ABORT, 'retry records are immutable'); END;

CREATE TRIGGER operator_retry_receipts_no_delete BEFORE DELETE ON operator_retry_receipts BEGIN SELECT RAISE(ABORT, 'retry records are immutable'); END;

CREATE TRIGGER operator_retry_receipts_no_replace BEFORE INSERT ON operator_retry_receipts WHEN EXISTS (SELECT 1 FROM operator_retry_receipts old WHERE old.receipt_id = NEW.receipt_id OR (old.tenant_id = NEW.tenant_id AND old.workflow_id = NEW.workflow_id AND old.idempotency_key = NEW.idempotency_key)) BEGIN SELECT RAISE(ABORT, 'retry identity already exists'); END;

CREATE TRIGGER operator_retry_audit_no_update BEFORE UPDATE ON agent_events WHEN json_extract(OLD.anchors_json, '$.proposal_contract') = 'workflow.operator-command-proposal.v5' OR EXISTS (SELECT 1 FROM operator_retry_receipts receipt WHERE OLD.id IN (receipt.command_event_id, receipt.lifecycle_event_id)) BEGIN SELECT RAISE(ABORT, 'retry audit is immutable'); END;

CREATE TRIGGER operator_retry_audit_no_delete BEFORE DELETE ON agent_events WHEN json_extract(OLD.anchors_json, '$.proposal_contract') = 'workflow.operator-command-proposal.v5' OR EXISTS (SELECT 1 FROM operator_retry_receipts receipt WHERE OLD.id IN (receipt.command_event_id, receipt.lifecycle_event_id)) BEGIN SELECT RAISE(ABORT, 'retry audit is immutable'); END;

CREATE TRIGGER operator_retry_audit_no_replace BEFORE INSERT ON agent_events WHEN EXISTS (SELECT 1 FROM agent_events old WHERE old.id = NEW.id AND (json_extract(old.anchors_json, '$.proposal_contract') = 'workflow.operator-command-proposal.v5' OR EXISTS (SELECT 1 FROM operator_retry_receipts receipt WHERE old.id IN (receipt.command_event_id, receipt.lifecycle_event_id)))) BEGIN SELECT RAISE(ABORT, 'retry audit identity already exists'); END;

CREATE VIEW operator_all_proposals_v5 AS SELECT * FROM operator_all_proposals_v4
UNION ALL SELECT proposal_id, tenant_id, workflow_id, principal_id, command_type, proposal_digest, proposal_json, active_graph_revision, source_run_status, source_run_state, snapshot_digest, snapshot_cursor, latest_event_id, latest_event_timestamp, harness_id, policy_profile_id, registry_version, registry_fingerprint, preflight_digest, idempotency_key, issued_at, expires_at, created_at FROM operator_retry_proposals;

CREATE VIEW operator_all_receipts_v5 AS SELECT * FROM operator_all_receipts_v4
UNION ALL SELECT receipt_id, proposal_id, tenant_id, workflow_id, principal_id, command_type, proposal_digest, idempotency_key, request_hash, outcome, prior_run_status, resulting_run_status, resulting_run_state, active_graph_revision, command_event_id, lifecycle_event_id, stopping_event_id, acknowledgement, propagation_state, receipt_json, receipt_digest, completed_at FROM operator_retry_receipts;
