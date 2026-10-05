-- Phase 2.4a: exact action reviews composed with existing approval authority.

CREATE TABLE IF NOT EXISTS operator_action_review_proposals (
    proposal_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    command_type TEXT NOT NULL CHECK (command_type IN ('approve', 'reject')),
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

CREATE TABLE IF NOT EXISTS operator_action_review_receipts (
    receipt_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    command_type TEXT NOT NULL CHECK (command_type IN ('approve', 'reject')),
    proposal_digest TEXT NOT NULL CHECK (length(proposal_digest) = 64),
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    outcome TEXT NOT NULL CHECK (outcome IN ('approved', 'rejected')),
    prior_run_status TEXT NOT NULL CHECK (prior_run_status IN ('planned', 'running', 'paused')),
    run_mode TEXT GENERATED ALWAYS AS (json_extract(receipt_json, '$.run_mode')) VIRTUAL NOT NULL CHECK (run_mode IN ('plan_only', 'auto_execute_safe')),
    resulting_run_status TEXT NOT NULL CHECK (resulting_run_status = prior_run_status),
    resulting_run_state TEXT NOT NULL,
    active_graph_revision INTEGER NOT NULL CHECK (active_graph_revision >= 1),
    command_event_id TEXT NOT NULL,
    lifecycle_event_id TEXT NOT NULL,
    stopping_event_id TEXT CHECK (stopping_event_id IS NULL),
    acknowledgement TEXT NOT NULL CHECK (acknowledgement = 'exact_action_decision_recorded'),
    propagation_state TEXT NOT NULL CHECK (
        propagation_state = 'runtime_propagation_not_certified'
    ),
    receipt_json TEXT NOT NULL CHECK (json_valid(receipt_json)),
    receipt_digest TEXT NOT NULL CHECK (length(receipt_digest) = 64),
    completed_at TEXT NOT NULL,
    approval_command_id TEXT GENERATED ALWAYS AS (json_extract(receipt_json, '$.approval_command_id')) VIRTUAL NOT NULL REFERENCES approval_commands(command_id) ON DELETE RESTRICT,
    FOREIGN KEY (proposal_id) REFERENCES operator_action_review_proposals(proposal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (principal_id) REFERENCES principals(id) ON DELETE RESTRICT,
    FOREIGN KEY (command_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (lifecycle_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (stopping_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key),
    CHECK (outcome IN ('approved', 'rejected'))
);


CREATE TRIGGER operator_action_review_proposal_scope
BEFORE INSERT ON operator_action_review_proposals
BEGIN
 SELECT CASE WHEN NOT EXISTS (
  SELECT 1 FROM agent_runs run JOIN agent_actions action ON action.agent_run_id = run.id
  JOIN principals human ON human.id = NEW.principal_id
  WHERE run.id = NEW.workflow_id AND run.client_id = NEW.tenant_id
   AND run.status = NEW.source_run_status AND run.state = NEW.source_run_state
   AND run.active_graph_revision = NEW.active_graph_revision AND run.lock_token IS NULL
   AND human.tenant_id = NEW.tenant_id AND human.principal_type = 'human' AND human.status = 'active'
   AND action.id = NEW.action_id AND action.status = 'proposed'
 ) THEN RAISE(ABORT, 'action review source changed') END;
 SELECT CASE WHEN json_extract(NEW.proposal_json, '$.contract') IS NOT 'workflow.operator-command-proposal.v4'
  OR json_extract(NEW.proposal_json, '$.proposal_id') IS NOT NEW.proposal_id
  OR json_extract(NEW.proposal_json, '$.tenant_id') IS NOT NEW.tenant_id
  OR json_extract(NEW.proposal_json, '$.run_id') IS NOT NEW.workflow_id
  OR json_extract(NEW.proposal_json, '$.principal_id') IS NOT NEW.principal_id
  OR json_extract(NEW.proposal_json, '$.command_type') IS NOT NEW.command_type
  OR json_extract(NEW.proposal_json, '$.proposal_digest') IS NOT NEW.proposal_digest
 THEN RAISE(ABORT, 'action review proposal identity changed') END;
END;

CREATE TRIGGER operator_action_review_receipt_scope
BEFORE INSERT ON operator_action_review_receipts
BEGIN
 SELECT CASE WHEN json_extract(NEW.receipt_json, '$.contract') IS NOT 'workflow.operator-command-receipt.v4'
  OR json_extract(NEW.receipt_json, '$.receipt_id') IS NOT NEW.receipt_id
  OR json_extract(NEW.receipt_json, '$.proposal_id') IS NOT NEW.proposal_id
  OR json_extract(NEW.receipt_json, '$.proposal_digest') IS NOT NEW.proposal_digest
  OR json_extract(NEW.receipt_json, '$.tenant_id') IS NOT NEW.tenant_id
  OR json_extract(NEW.receipt_json, '$.run_id') IS NOT NEW.workflow_id
  OR json_extract(NEW.receipt_json, '$.principal_id') IS NOT NEW.principal_id
  OR json_extract(NEW.receipt_json, '$.command_type') IS NOT NEW.command_type
  OR json_extract(NEW.receipt_json, '$.idempotency_key') IS NOT NEW.idempotency_key
  OR json_extract(NEW.receipt_json, '$.receipt_digest') IS NOT NEW.receipt_digest
 THEN RAISE(ABORT, 'action review receipt identity changed') END;
 SELECT CASE WHEN NOT EXISTS (
  SELECT 1 FROM approval_commands command
  JOIN operator_action_review_proposals proposal ON proposal.proposal_id = NEW.proposal_id
  JOIN agent_runs run ON run.id = NEW.workflow_id AND run.client_id = NEW.tenant_id
  JOIN agent_events audit ON audit.id = NEW.command_event_id
  JOIN agent_events lifecycle ON lifecycle.id = NEW.lifecycle_event_id
  WHERE command.command_id = NEW.approval_command_id
   AND command.tenant_id = NEW.tenant_id AND command.workflow_id = NEW.workflow_id
   AND command.principal_type = 'human' AND command.principal_id = NEW.principal_id
   AND command.command_type = NEW.command_type AND command.status = 'committed'
   AND command.idempotency_key = NEW.idempotency_key
   AND proposal.tenant_id = NEW.tenant_id AND proposal.workflow_id = NEW.workflow_id
   AND proposal.principal_id = NEW.principal_id AND proposal.command_type = NEW.command_type
   AND proposal.proposal_digest = NEW.proposal_digest AND proposal.action_id = command.action_id
   AND json_extract(NEW.receipt_json, '$.action_id') = command.action_id
   AND run.status = NEW.resulting_run_status AND run.state = NEW.resulting_run_state
   AND json_extract(command.result_json, '$.approval.status') = NEW.outcome
   AND json_extract(command.result_json, '$.approval.approval_id') = json_extract(NEW.receipt_json, '$.approval_id')
   AND json_extract(command.result_json, '$.approval.envelope_digest') = json_extract(NEW.receipt_json, '$.approval_envelope_digest')
   AND json_extract(command.result_json, '$.approval.sequence') = json_extract(NEW.receipt_json, '$.approval_sequence')
   AND audit.agent_run_id = NEW.workflow_id AND audit.principal_id = NEW.principal_id
   AND audit.event_type = 'operator_command_' || NEW.command_type
   AND json_extract(audit.anchors_json, '$.proposal_id') = NEW.proposal_id
   AND json_extract(audit.anchors_json, '$.receipt_id') = NEW.receipt_id
   AND lifecycle.agent_run_id = NEW.workflow_id AND lifecycle.action_id = command.action_id
   AND json_extract(lifecycle.anchors_json, '$.approval_command_id') = command.command_id
 ) THEN RAISE(ABORT, 'action review receipt has no exact approval authority') END;
END;

CREATE INDEX operator_action_review_proposals_scope ON operator_action_review_proposals(tenant_id, workflow_id, created_at, proposal_id);
CREATE INDEX operator_action_review_receipts_scope ON operator_action_review_receipts(tenant_id, workflow_id, completed_at, receipt_id);

CREATE TRIGGER operator_action_review_proposals_no_update BEFORE UPDATE ON operator_action_review_proposals BEGIN SELECT RAISE(ABORT, 'action review records are immutable'); END;

CREATE TRIGGER operator_action_review_proposals_no_delete BEFORE DELETE ON operator_action_review_proposals BEGIN SELECT RAISE(ABORT, 'action review records are immutable'); END;

CREATE TRIGGER operator_action_review_proposals_no_replace BEFORE INSERT ON operator_action_review_proposals WHEN EXISTS (SELECT 1 FROM operator_action_review_proposals old WHERE old.proposal_id = NEW.proposal_id OR (old.tenant_id = NEW.tenant_id AND old.workflow_id = NEW.workflow_id AND old.idempotency_key = NEW.idempotency_key)) BEGIN SELECT RAISE(ABORT, 'action review identity already exists'); END;

CREATE TRIGGER operator_action_review_receipts_no_update BEFORE UPDATE ON operator_action_review_receipts BEGIN SELECT RAISE(ABORT, 'action review records are immutable'); END;

CREATE TRIGGER operator_action_review_receipts_no_delete BEFORE DELETE ON operator_action_review_receipts BEGIN SELECT RAISE(ABORT, 'action review records are immutable'); END;

CREATE TRIGGER operator_action_review_receipts_no_replace BEFORE INSERT ON operator_action_review_receipts WHEN EXISTS (SELECT 1 FROM operator_action_review_receipts old WHERE old.receipt_id = NEW.receipt_id OR (old.tenant_id = NEW.tenant_id AND old.workflow_id = NEW.workflow_id AND old.idempotency_key = NEW.idempotency_key)) BEGIN SELECT RAISE(ABORT, 'action review identity already exists'); END;

CREATE TRIGGER operator_action_review_audit_no_update BEFORE UPDATE ON agent_events WHEN json_extract(OLD.anchors_json, '$.proposal_contract') = 'workflow.operator-command-proposal.v4' OR EXISTS (SELECT 1 FROM operator_action_review_receipts receipt WHERE OLD.id IN (receipt.command_event_id, receipt.lifecycle_event_id)) BEGIN SELECT RAISE(ABORT, 'action review audit is immutable'); END;

CREATE TRIGGER operator_action_review_audit_no_delete BEFORE DELETE ON agent_events WHEN json_extract(OLD.anchors_json, '$.proposal_contract') = 'workflow.operator-command-proposal.v4' OR EXISTS (SELECT 1 FROM operator_action_review_receipts receipt WHERE OLD.id IN (receipt.command_event_id, receipt.lifecycle_event_id)) BEGIN SELECT RAISE(ABORT, 'action review audit is immutable'); END;

CREATE TRIGGER operator_action_review_audit_no_replace BEFORE INSERT ON agent_events WHEN EXISTS (SELECT 1 FROM agent_events old WHERE old.id = NEW.id AND (json_extract(old.anchors_json, '$.proposal_contract') = 'workflow.operator-command-proposal.v4' OR EXISTS (SELECT 1 FROM operator_action_review_receipts receipt WHERE old.id IN (receipt.command_event_id, receipt.lifecycle_event_id)))) BEGIN SELECT RAISE(ABORT, 'action review audit identity already exists'); END;

CREATE VIEW operator_all_proposals_v4 AS SELECT * FROM operator_all_proposals_v3
UNION ALL SELECT proposal_id, tenant_id, workflow_id, principal_id, command_type, proposal_digest, proposal_json, active_graph_revision, source_run_status, source_run_state, snapshot_digest, snapshot_cursor, latest_event_id, latest_event_timestamp, harness_id, policy_profile_id, registry_version, registry_fingerprint, preflight_digest, idempotency_key, issued_at, expires_at, created_at FROM operator_action_review_proposals;

CREATE VIEW operator_all_receipts_v4 AS SELECT * FROM operator_all_receipts_v3
UNION ALL SELECT receipt_id, proposal_id, tenant_id, workflow_id, principal_id, command_type, proposal_digest, idempotency_key, request_hash, outcome, prior_run_status, resulting_run_status, resulting_run_state, active_graph_revision, command_event_id, lifecycle_event_id, stopping_event_id, acknowledgement, propagation_state, receipt_json, receipt_digest, completed_at FROM operator_action_review_receipts;
