-- Slice 6c: atomic durable completion decisions and compatibility projections.

-- This table is intentionally not backfilled. Databases that already applied
-- Slice 6b can roll through a mixed-version deployment without making the old
-- writer fail. New publications and the new lifecycle commit path activate the
-- guard monotonically.
CREATE TABLE IF NOT EXISTS workflow_completion_governance (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    criteria_digest TEXT NOT NULL,
    activation_command_id TEXT NOT NULL,
    activated_at TEXT NOT NULL,
    governance_version INTEGER NOT NULL DEFAULT 1 CHECK (governance_version > 0),
    PRIMARY KEY (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (criteria_digest)
        REFERENCES workflow_completion_criteria(criteria_digest) ON DELETE RESTRICT,
    FOREIGN KEY (activation_command_id)
        REFERENCES workflow_outcome_commands(command_id) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_completion_governance_binding_guard_insert
BEFORE INSERT ON workflow_completion_governance
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_criteria criteria
        JOIN workflow_outcome_commands command
          ON command.command_id = NEW.activation_command_id
        WHERE criteria.criteria_digest = NEW.criteria_digest
          AND criteria.tenant_id = NEW.tenant_id
          AND criteria.workflow_id = NEW.workflow_id
          AND criteria.graph_revision = NEW.graph_revision
          AND command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.artifact_type IN (
              'completion_contract', 'completion_decision'
          )
    ) THEN RAISE(ABORT, 'completion governance authority is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_governance_binding_guard_update
BEFORE UPDATE ON workflow_completion_governance
BEGIN
    SELECT CASE WHEN NEW.governance_version <> OLD.governance_version + 1
      OR NEW.graph_revision < OLD.graph_revision
      OR NEW.activated_at <= OLD.activated_at
      OR NOT EXISTS (
        SELECT 1
        FROM workflow_completion_criteria criteria
        JOIN workflow_outcome_commands command
          ON command.command_id = NEW.activation_command_id
        WHERE criteria.criteria_digest = NEW.criteria_digest
          AND criteria.tenant_id = NEW.tenant_id
          AND criteria.workflow_id = NEW.workflow_id
          AND criteria.graph_revision = NEW.graph_revision
          AND command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.artifact_type = 'completion_contract'
          AND command.artifact_digest = NEW.criteria_digest
    ) THEN RAISE(ABORT, 'completion governance update is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_governance_no_delete
BEFORE DELETE ON workflow_completion_governance
BEGIN
    SELECT RAISE(ABORT, 'workflow completion governance is monotonic');
END;

CREATE TABLE IF NOT EXISTS workflow_completion_event_cursors (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    current_sequence INTEGER NOT NULL DEFAULT -1 CHECK (current_sequence >= -1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS workflow_completion_attempt_authorities (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    task_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    assignment_id TEXT,
    producer_principal_id TEXT NOT NULL,
    action_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, workflow_id, graph_revision, task_id),
    UNIQUE (tenant_id, workflow_id, attempt_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_completion_attempt_authority_no_update
BEFORE UPDATE ON workflow_completion_attempt_authorities
BEGIN
    SELECT RAISE(ABORT, 'workflow completion attempt authority is immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_attempt_authority_no_delete
BEFORE DELETE ON workflow_completion_attempt_authorities
BEGIN
    SELECT RAISE(ABORT, 'workflow completion attempt authority is immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_event_cursor_no_delete
BEFORE DELETE ON workflow_completion_event_cursors
BEGIN
    SELECT RAISE(ABORT, 'workflow completion event cursor is monotonic');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_event_cursor_increment_guard
BEFORE UPDATE OF current_sequence ON workflow_completion_event_cursors
WHEN NEW.current_sequence <> OLD.current_sequence + 1
BEGIN
    SELECT RAISE(ABORT, 'workflow completion event cursor must increment by one');
END;

CREATE TABLE IF NOT EXISTS workflow_completion_lifecycle_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    decision_id TEXT NOT NULL UNIQUE,
    decision_digest TEXT NOT NULL UNIQUE,
    completion_status TEXT NOT NULL CHECK (
        completion_status IN ('complete', 'incomplete')
    ),
    prior_run_status TEXT NOT NULL,
    projected_run_status TEXT NOT NULL,
    prior_run_state TEXT NOT NULL,
    projected_run_state TEXT NOT NULL,
    action_projection_digest TEXT NOT NULL,
    authoritative_event_sequence INTEGER NOT NULL CHECK (
        authoritative_event_sequence >= 0
    ),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    command_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (decision_id)
        REFERENCES workflow_completion_decisions(decision_id) ON DELETE RESTRICT,
    FOREIGN KEY (command_id)
        REFERENCES workflow_outcome_commands(command_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_workflow_completion_lifecycle_scope
    ON workflow_completion_lifecycle_events(
        tenant_id, workflow_id, graph_revision, created_at
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_completion_lifecycle_sequence
    ON workflow_completion_lifecycle_events(
        tenant_id, workflow_id, authoritative_event_sequence
    );

CREATE TRIGGER IF NOT EXISTS workflow_completion_lifecycle_binding_guard
BEFORE INSERT ON workflow_completion_lifecycle_events
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_decisions decision
        JOIN workflow_outcome_commands command
          ON command.command_id = NEW.command_id
        WHERE decision.decision_id = NEW.decision_id
          AND decision.decision_digest = NEW.decision_digest
          AND decision.tenant_id = NEW.tenant_id
          AND decision.workflow_id = NEW.workflow_id
          AND decision.graph_revision = NEW.graph_revision
          AND decision.status = NEW.completion_status
          AND decision.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND decision.command_id = NEW.command_id
          AND command.artifact_type = 'completion_decision'
          AND command.artifact_id = NEW.decision_id
          AND command.artifact_digest = NEW.decision_digest
    ) THEN RAISE(ABORT, 'completion lifecycle decision binding is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_completion_projections (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    decision_id TEXT NOT NULL,
    decision_digest TEXT NOT NULL,
    criteria_digest TEXT NOT NULL,
    completion_status TEXT NOT NULL CHECK (
        completion_status IN ('complete', 'incomplete')
    ),
    projected_run_status TEXT NOT NULL,
    projected_run_state TEXT NOT NULL,
    authoritative_event_sequence INTEGER NOT NULL CHECK (
        authoritative_event_sequence >= 0
    ),
    action_projection_digest TEXT NOT NULL,
    blockers_json TEXT NOT NULL CHECK (json_valid(blockers_json)),
    evaluated_at TEXT NOT NULL,
    projection_version INTEGER NOT NULL DEFAULT 1 CHECK (projection_version > 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, workflow_id),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (decision_id)
        REFERENCES workflow_completion_decisions(decision_id) ON DELETE RESTRICT,
    FOREIGN KEY (criteria_digest)
        REFERENCES workflow_completion_criteria(criteria_digest) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_completion_projection_decision_guard_insert
BEFORE INSERT ON workflow_completion_projections
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_completion_decisions decision
        WHERE decision.decision_id = NEW.decision_id
          AND decision.decision_digest = NEW.decision_digest
          AND decision.criteria_digest = NEW.criteria_digest
          AND decision.tenant_id = NEW.tenant_id
          AND decision.workflow_id = NEW.workflow_id
          AND decision.graph_revision = NEW.graph_revision
          AND decision.status = NEW.completion_status
          AND decision.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND decision.evaluated_at = NEW.evaluated_at
    ) THEN RAISE(ABORT, 'completion projection decision binding is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_projection_decision_guard_update
BEFORE UPDATE ON workflow_completion_projections
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_completion_decisions decision
        WHERE decision.decision_id = NEW.decision_id
          AND decision.decision_digest = NEW.decision_digest
          AND decision.criteria_digest = NEW.criteria_digest
          AND decision.tenant_id = NEW.tenant_id
          AND decision.workflow_id = NEW.workflow_id
          AND decision.graph_revision = NEW.graph_revision
          AND decision.status = NEW.completion_status
          AND decision.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND decision.evaluated_at = NEW.evaluated_at
    ) THEN RAISE(ABORT, 'completion projection decision binding is invalid') END;
    SELECT CASE WHEN NEW.authoritative_event_sequence
                          <= OLD.authoritative_event_sequence
      OR NEW.evaluated_at < OLD.evaluated_at
    THEN RAISE(ABORT, 'completion projection cannot move backward') END;
END;

CREATE TRIGGER IF NOT EXISTS governed_agent_run_completion_guard
BEFORE UPDATE OF status ON agent_runs
WHEN NEW.status = 'completed'
 AND OLD.status <> 'completed'
 AND EXISTS (
    SELECT 1 FROM workflow_completion_governance governance
    WHERE governance.tenant_id = NEW.client_id
      AND governance.workflow_id = NEW.id
 )
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_projections projection
        JOIN workflow_completion_decisions decision
          ON decision.decision_id = projection.decision_id
         AND decision.decision_digest = projection.decision_digest
        WHERE projection.tenant_id = NEW.client_id
          AND projection.workflow_id = NEW.id
          AND projection.graph_revision = NEW.active_graph_revision
          AND projection.completion_status = 'complete'
          AND projection.projected_run_status = 'completed'
          AND decision.status = 'complete'
          AND EXISTS (
              SELECT 1 FROM workflow_completion_governance governance
              WHERE governance.tenant_id = NEW.client_id
                AND governance.workflow_id = NEW.id
                AND governance.graph_revision = NEW.active_graph_revision
                AND governance.criteria_digest = decision.criteria_digest
          )
    ) THEN RAISE(ABORT, 'governed run requires an exact COMPLETE decision') END;
END;

CREATE TRIGGER IF NOT EXISTS governed_agent_run_terminal_guard
BEFORE UPDATE OF status ON agent_runs
WHEN OLD.status IN ('completed', 'canceled', 'cancelled')
 AND NEW.status <> OLD.status
 AND EXISTS (
    SELECT 1 FROM workflow_completion_governance governance
    WHERE governance.tenant_id = OLD.client_id
      AND governance.workflow_id = OLD.id
 )
BEGIN
    SELECT RAISE(ABORT, 'governed terminal run status is immutable');
END;

CREATE TRIGGER IF NOT EXISTS governed_terminal_run_action_guard
BEFORE INSERT ON agent_actions
WHEN EXISTS (
    SELECT 1
    FROM agent_runs run
    JOIN workflow_completion_governance governance
      ON governance.tenant_id = run.client_id
     AND governance.workflow_id = run.id
    WHERE run.id = NEW.agent_run_id
      AND run.status IN ('completed', 'canceled', 'cancelled')
)
BEGIN
    SELECT RAISE(ABORT, 'governed terminal run cannot acquire new actions');
END;

CREATE TRIGGER IF NOT EXISTS agent_action_status_contract_insert
BEFORE INSERT ON agent_actions
WHEN NEW.status NOT IN (
    'proposed', 'approved', 'rejected', 'executing', 'executed', 'failed'
)
BEGIN
    SELECT RAISE(ABORT, 'agent action status is outside the closed lifecycle');
END;

CREATE TRIGGER IF NOT EXISTS agent_action_status_contract_update
BEFORE UPDATE OF status ON agent_actions
WHEN NEW.status NOT IN (
    'proposed', 'approved', 'rejected', 'executing', 'executed', 'failed'
)
BEGIN
    SELECT RAISE(ABORT, 'agent action status is outside the closed lifecycle');
END;

CREATE TRIGGER IF NOT EXISTS governed_terminal_run_action_update_guard
BEFORE UPDATE ON agent_actions
WHEN EXISTS (
    SELECT 1
    FROM agent_runs run
    JOIN workflow_completion_governance governance
      ON governance.tenant_id = run.client_id
     AND governance.workflow_id = run.id
    WHERE run.id = OLD.agent_run_id
      AND run.status IN ('completed', 'canceled', 'cancelled')
)
BEGIN
    SELECT RAISE(ABORT, 'governed terminal run action status is immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_lifecycle_events_no_update
BEFORE UPDATE ON workflow_completion_lifecycle_events
BEGIN
    SELECT RAISE(ABORT, 'workflow completion lifecycle events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_lifecycle_events_no_delete
BEFORE DELETE ON workflow_completion_lifecycle_events
BEGIN
    SELECT RAISE(ABORT, 'workflow completion lifecycle events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_projections_no_delete
BEFORE DELETE ON workflow_completion_projections
BEGIN
    SELECT RAISE(ABORT, 'workflow completion projections are retained for recovery');
END;
