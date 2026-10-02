-- Phase 2.2: immutable conversational pause proposals and receipts.

CREATE TABLE IF NOT EXISTS operator_command_proposals (
    proposal_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    command_type TEXT NOT NULL CHECK (command_type = 'pause'),
    proposal_digest TEXT NOT NULL CHECK (length(proposal_digest) = 64),
    proposal_json TEXT NOT NULL CHECK (json_valid(proposal_json)),
    active_graph_revision INTEGER NOT NULL CHECK (active_graph_revision >= 1),
    source_run_status TEXT NOT NULL,
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
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (principal_id) REFERENCES principals(id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key),
    CHECK (
        (latest_event_id IS NULL AND latest_event_timestamp IS NULL)
        OR (latest_event_id IS NOT NULL AND latest_event_timestamp IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_operator_command_proposals_scope
ON operator_command_proposals(tenant_id, workflow_id, created_at DESC);

CREATE TABLE IF NOT EXISTS operator_command_receipts (
    receipt_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    command_type TEXT NOT NULL CHECK (command_type = 'pause'),
    proposal_digest TEXT NOT NULL CHECK (length(proposal_digest) = 64),
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    outcome TEXT NOT NULL CHECK (outcome = 'paused'),
    prior_run_status TEXT NOT NULL,
    resulting_run_status TEXT NOT NULL CHECK (resulting_run_status = 'paused'),
    resulting_run_state TEXT NOT NULL,
    active_graph_revision INTEGER NOT NULL CHECK (active_graph_revision >= 1),
    command_event_id TEXT NOT NULL,
    lifecycle_event_id TEXT NOT NULL,
    stopping_event_id TEXT,
    acknowledgement TEXT NOT NULL CHECK (acknowledgement = 'control_plane_paused'),
    propagation_state TEXT NOT NULL CHECK (
        propagation_state = 'runtime_propagation_not_certified'
    ),
    receipt_json TEXT NOT NULL CHECK (json_valid(receipt_json)),
    receipt_digest TEXT NOT NULL CHECK (length(receipt_digest) = 64),
    completed_at TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES operator_command_proposals(proposal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (principal_id) REFERENCES principals(id) ON DELETE RESTRICT,
    FOREIGN KEY (command_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (lifecycle_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (stopping_event_id) REFERENCES agent_events(id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_operator_command_receipts_scope
ON operator_command_receipts(tenant_id, workflow_id, completed_at DESC);

CREATE TRIGGER IF NOT EXISTS operator_command_proposals_guard_insert
BEFORE INSERT ON operator_command_proposals
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM agent_runs run
        WHERE run.id = NEW.workflow_id
          AND run.client_id = NEW.tenant_id
          AND run.active_graph_revision = NEW.active_graph_revision
          AND run.status = NEW.source_run_status
          AND run.state = NEW.source_run_state
          AND run.harness_id IS NEW.harness_id
          AND run.policy_profile_id IS NEW.policy_profile_id
          AND run.registry_version IS NEW.registry_version
          AND run.registry_fingerprint IS NEW.registry_fingerprint
    ) THEN RAISE(ABORT, 'operator command proposal source changed') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM principals principal
        WHERE principal.id = NEW.principal_id
          AND principal.principal_type = 'human'
          AND principal.tenant_id = NEW.tenant_id
          AND principal.status = 'active'
    ) THEN RAISE(ABORT, 'operator command proposal principal is invalid') END;

    SELECT CASE WHEN json_extract(NEW.proposal_json, '$.proposal_id') <> NEW.proposal_id
      OR json_extract(NEW.proposal_json, '$.tenant_id') <> NEW.tenant_id
      OR json_extract(NEW.proposal_json, '$.run_id') <> NEW.workflow_id
      OR json_extract(NEW.proposal_json, '$.principal_id') <> NEW.principal_id
      OR json_extract(NEW.proposal_json, '$.command_type') <> NEW.command_type
      OR json_extract(NEW.proposal_json, '$.proposal_digest') <> NEW.proposal_digest
      OR json_extract(NEW.proposal_json, '$.preflight.digest') <> NEW.preflight_digest
    THEN RAISE(ABORT, 'operator command proposal columns contradict payload') END;
END;

CREATE TRIGGER IF NOT EXISTS operator_command_proposals_no_update
BEFORE UPDATE ON operator_command_proposals
BEGIN
    SELECT RAISE(ABORT, 'operator command proposals are immutable');
END;

CREATE TRIGGER IF NOT EXISTS operator_command_proposals_no_delete
BEFORE DELETE ON operator_command_proposals
BEGIN
    SELECT RAISE(ABORT, 'operator command proposals are immutable');
END;

CREATE TRIGGER IF NOT EXISTS operator_command_proposals_no_replace
BEFORE INSERT ON operator_command_proposals
WHEN EXISTS (
    SELECT 1 FROM operator_command_proposals existing
    WHERE existing.proposal_id = NEW.proposal_id
       OR (existing.tenant_id = NEW.tenant_id
           AND existing.workflow_id = NEW.workflow_id
           AND existing.idempotency_key = NEW.idempotency_key)
)
BEGIN
    SELECT RAISE(ABORT, 'operator command proposal identity already exists');
END;

CREATE TRIGGER IF NOT EXISTS operator_command_receipts_guard_insert
BEFORE INSERT ON operator_command_receipts
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM operator_command_proposals proposal
        WHERE proposal.proposal_id = NEW.proposal_id
          AND proposal.tenant_id = NEW.tenant_id
          AND proposal.workflow_id = NEW.workflow_id
          AND proposal.principal_id = NEW.principal_id
          AND proposal.command_type = NEW.command_type
          AND proposal.proposal_digest = NEW.proposal_digest
          AND proposal.idempotency_key = NEW.idempotency_key
    ) THEN RAISE(ABORT, 'operator command receipt proposal is invalid') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM agent_runs run
        WHERE run.id = NEW.workflow_id
          AND run.client_id = NEW.tenant_id
          AND run.status = NEW.resulting_run_status
          AND run.state = NEW.resulting_run_state
          AND run.active_graph_revision = NEW.active_graph_revision
    ) THEN RAISE(ABORT, 'operator command receipt run result is invalid') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM agent_events command_event
        WHERE command_event.id = NEW.command_event_id
          AND command_event.agent_run_id = NEW.workflow_id
          AND command_event.event_type = 'operator_command_pause'
          AND command_event.status = 'completed'
          AND command_event.principal_type = 'human'
          AND command_event.principal_id = NEW.principal_id
          AND json_extract(command_event.anchors_json, '$.proposal_id') = NEW.proposal_id
          AND json_extract(command_event.anchors_json, '$.proposal_digest') = NEW.proposal_digest
          AND json_extract(command_event.anchors_json, '$.receipt_id') = NEW.receipt_id
    ) THEN RAISE(ABORT, 'operator command receipt audit is invalid') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM agent_events lifecycle
        WHERE lifecycle.id = NEW.lifecycle_event_id
          AND lifecycle.agent_run_id = NEW.workflow_id
          AND lifecycle.event_type = 'run_paused'
          AND lifecycle.status = 'paused'
          AND json_extract(lifecycle.anchors_json, '$.proposal_id') = NEW.proposal_id
          AND json_extract(lifecycle.anchors_json, '$.receipt_id') = NEW.receipt_id
    ) THEN RAISE(ABORT, 'operator command lifecycle audit is invalid') END;

    SELECT CASE WHEN NEW.stopping_event_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM agent_events stopping
        WHERE stopping.id = NEW.stopping_event_id
          AND stopping.agent_run_id = NEW.workflow_id
          AND stopping.event_type = 'run_stopping_condition_met'
          AND stopping.status = 'paused'
          AND json_extract(stopping.anchors_json, '$.stopping_condition') = 'operator_pause'
          AND json_extract(stopping.anchors_json, '$.proposal_id') = NEW.proposal_id
          AND json_extract(stopping.anchors_json, '$.receipt_id') = NEW.receipt_id
    ) THEN RAISE(ABORT, 'operator command stopping audit is invalid') END;

    SELECT CASE WHEN json_extract(NEW.receipt_json, '$.receipt_id') <> NEW.receipt_id
      OR json_extract(NEW.receipt_json, '$.proposal_id') <> NEW.proposal_id
      OR json_extract(NEW.receipt_json, '$.proposal_digest') <> NEW.proposal_digest
      OR json_extract(NEW.receipt_json, '$.tenant_id') <> NEW.tenant_id
      OR json_extract(NEW.receipt_json, '$.run_id') <> NEW.workflow_id
      OR json_extract(NEW.receipt_json, '$.principal_id') <> NEW.principal_id
      OR json_extract(NEW.receipt_json, '$.request_hash') <> NEW.request_hash
      OR json_extract(NEW.receipt_json, '$.receipt_digest') <> NEW.receipt_digest
    THEN RAISE(ABORT, 'operator command receipt columns contradict payload') END;
END;

CREATE TRIGGER IF NOT EXISTS operator_command_receipts_no_update
BEFORE UPDATE ON operator_command_receipts
BEGIN
    SELECT RAISE(ABORT, 'operator command receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS operator_command_receipts_no_delete
BEFORE DELETE ON operator_command_receipts
BEGIN
    SELECT RAISE(ABORT, 'operator command receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS operator_command_receipts_no_replace
BEFORE INSERT ON operator_command_receipts
WHEN EXISTS (
    SELECT 1 FROM operator_command_receipts existing
    WHERE existing.receipt_id = NEW.receipt_id
       OR existing.proposal_id = NEW.proposal_id
       OR (existing.tenant_id = NEW.tenant_id
           AND existing.workflow_id = NEW.workflow_id
           AND existing.idempotency_key = NEW.idempotency_key)
)
BEGIN
    SELECT RAISE(ABORT, 'operator command receipt identity already exists');
END;

CREATE TRIGGER IF NOT EXISTS conversational_pause_audits_no_update
BEFORE UPDATE ON agent_events
WHEN OLD.event_type IN (
    'operator_command_pause', 'run_paused', 'run_stopping_condition_met'
)
  AND json_extract(OLD.anchors_json, '$.proposal_contract') =
      'workflow.operator-command-proposal.v1'
BEGIN
    SELECT RAISE(ABORT, 'conversational pause audit events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS conversational_pause_audits_no_delete
BEFORE DELETE ON agent_events
WHEN OLD.event_type IN (
    'operator_command_pause', 'run_paused', 'run_stopping_condition_met'
)
  AND json_extract(OLD.anchors_json, '$.proposal_contract') =
      'workflow.operator-command-proposal.v1'
BEGIN
    SELECT RAISE(ABORT, 'conversational pause audit events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS conversational_pause_audits_no_replace
BEFORE INSERT ON agent_events
WHEN EXISTS (
    SELECT 1 FROM agent_events existing
    WHERE existing.id = NEW.id
      AND existing.event_type IN (
          'operator_command_pause', 'run_paused', 'run_stopping_condition_met'
      )
      AND json_extract(existing.anchors_json, '$.proposal_contract') =
          'workflow.operator-command-proposal.v1'
)
BEGIN
    SELECT RAISE(ABORT, 'conversational pause audit event identity already exists');
END;
