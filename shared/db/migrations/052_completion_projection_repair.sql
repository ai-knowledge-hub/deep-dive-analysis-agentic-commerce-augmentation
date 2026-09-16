-- Slice 6d.1: immutable operator receipts for completion-projection repair.

CREATE TABLE IF NOT EXISTS workflow_completion_projection_repairs (
    command_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    principal_type TEXT NOT NULL CHECK (principal_type = 'human'),
    principal_id TEXT NOT NULL,
    authority_source TEXT NOT NULL,
    authority_version TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('repaired', 'already_current')),
    lifecycle_event_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    decision_digest TEXT NOT NULL,
    authoritative_event_sequence INTEGER NOT NULL CHECK (
        authoritative_event_sequence >= 0
    ),
    prior_projection_version INTEGER,
    resulting_projection_version INTEGER NOT NULL CHECK (
        resulting_projection_version > 0
    ),
    completed_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (lifecycle_event_id)
        REFERENCES workflow_completion_lifecycle_events(event_id) ON DELETE RESTRICT,
    FOREIGN KEY (decision_id)
        REFERENCES workflow_completion_decisions(decision_id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_completion_projection_repairs_scope
ON workflow_completion_projection_repairs(
    tenant_id, workflow_id, completed_at DESC
);

CREATE TRIGGER IF NOT EXISTS completion_projection_repairs_no_update
BEFORE UPDATE ON workflow_completion_projection_repairs
BEGIN
    SELECT RAISE(ABORT, 'completion projection repair receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS completion_projection_repairs_no_delete
BEFORE DELETE ON workflow_completion_projection_repairs
BEGIN
    SELECT RAISE(ABORT, 'completion projection repair receipts are immutable');
END;

-- SEC-18 remains planned for the general event stream. This slice narrows its
-- stronger retention guarantee to the audit evidence required by projection
-- repair so a validated receipt cannot outlive or diverge from its audit row.
CREATE TRIGGER IF NOT EXISTS completion_projection_repair_audits_no_update
BEFORE UPDATE ON agent_events
WHEN OLD.event_type = 'completion_projection_repaired'
  OR NEW.event_type = 'completion_projection_repaired'
BEGIN
    SELECT RAISE(ABORT, 'completion projection repair audit events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS completion_projection_repair_audits_no_delete
BEFORE DELETE ON agent_events
WHEN OLD.event_type = 'completion_projection_repaired'
BEGIN
    SELECT RAISE(ABORT, 'completion projection repair audit events are immutable');
END;

-- SQLite REPLACE deletes a conflicting row without invoking its DELETE trigger
-- when recursive triggers are disabled. Inspect the pre-existing row during
-- BEFORE INSERT so changing the incoming event type cannot bypass retention.
CREATE TRIGGER IF NOT EXISTS completion_projection_repair_audits_no_replace
BEFORE INSERT ON agent_events
WHEN EXISTS (
    SELECT 1 FROM agent_events existing
    WHERE existing.id = NEW.id
      AND existing.event_type = 'completion_projection_repaired'
)
BEGIN
    SELECT RAISE(ABORT, 'completion projection repair audit events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS completion_projection_repairs_guard_insert
BEFORE INSERT ON workflow_completion_projection_repairs
BEGIN
    SELECT CASE WHEN NEW.authority_source <> 'agent-principal-token'
      OR NEW.authority_version <> 'agent-principal-signing-secret:v1'
    THEN RAISE(ABORT, 'completion projection repair authority is invalid') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM principals principal
        JOIN agent_runs run
          ON run.client_id = principal.tenant_id
         AND run.id = NEW.workflow_id
        WHERE principal.id = NEW.principal_id
          AND principal.principal_type = NEW.principal_type
          AND principal.principal_type = 'human'
          AND principal.tenant_id = NEW.tenant_id
          AND principal.status = 'active'
          AND json_extract(principal.metadata_json, '$.auth_method') = 'bearer_token'
          AND EXISTS (
              SELECT 1 FROM json_each(principal.metadata_json, '$.scopes') scope
              WHERE scope.value IN ('completion_projections:repair', '*')
          )
          AND (
              run.principal_id = principal.id
              OR EXISTS (
                  SELECT 1 FROM json_each(principal.metadata_json, '$.scopes') scope
                  WHERE scope.value IN ('agent_runs:supervise', '*')
              )
          )
    ) THEN RAISE(ABORT, 'completion projection repair operator is invalid') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_lifecycle_events lifecycle
        JOIN workflow_completion_decisions decision
          ON decision.decision_id = lifecycle.decision_id
         AND decision.decision_digest = lifecycle.decision_digest
        JOIN workflow_completion_event_cursors cursor
          ON cursor.tenant_id = lifecycle.tenant_id
         AND cursor.workflow_id = lifecycle.workflow_id
         AND cursor.current_sequence = lifecycle.authoritative_event_sequence
        WHERE lifecycle.event_id = NEW.lifecycle_event_id
          AND lifecycle.tenant_id = NEW.tenant_id
          AND lifecycle.workflow_id = NEW.workflow_id
          AND lifecycle.decision_id = NEW.decision_id
          AND lifecycle.decision_digest = NEW.decision_digest
          AND lifecycle.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND decision.tenant_id = NEW.tenant_id
          AND decision.workflow_id = NEW.workflow_id
          AND decision.authoritative_event_sequence = NEW.authoritative_event_sequence
    ) THEN RAISE(ABORT, 'completion projection repair lifecycle is invalid') END;

    SELECT CASE WHEN NOT (
        (
            NEW.outcome = 'repaired'
            AND (
                (
                    NEW.prior_projection_version IS NULL
                    AND NEW.resulting_projection_version = 1
                    AND NOT EXISTS (
                        SELECT 1 FROM workflow_completion_projections projection
                        WHERE projection.tenant_id = NEW.tenant_id
                          AND projection.workflow_id = NEW.workflow_id
                    )
                )
                OR EXISTS (
                    SELECT 1 FROM workflow_completion_projections projection
                    WHERE projection.tenant_id = NEW.tenant_id
                      AND projection.workflow_id = NEW.workflow_id
                      AND projection.projection_version = NEW.prior_projection_version
                      AND NEW.resulting_projection_version = projection.projection_version + 1
                )
            )
        )
        OR (
            NEW.outcome = 'already_current'
            AND EXISTS (
                SELECT 1 FROM workflow_completion_projections projection
                WHERE projection.tenant_id = NEW.tenant_id
                  AND projection.workflow_id = NEW.workflow_id
                  AND projection.projection_version = NEW.prior_projection_version
                  AND NEW.resulting_projection_version = projection.projection_version
            )
        )
    ) THEN RAISE(ABORT, 'completion projection repair version is invalid') END;

    SELECT CASE WHEN NEW.outcome = 'repaired' AND EXISTS (
        SELECT 1
        FROM workflow_completion_projections projection
        JOIN workflow_completion_lifecycle_events lifecycle
          ON lifecycle.event_id = NEW.lifecycle_event_id
        JOIN workflow_completion_decisions decision
          ON decision.decision_id = NEW.decision_id
        WHERE projection.tenant_id = NEW.tenant_id
          AND projection.workflow_id = NEW.workflow_id
          AND projection.graph_revision = lifecycle.graph_revision
          AND projection.decision_id = NEW.decision_id
          AND projection.decision_digest = NEW.decision_digest
          AND projection.criteria_digest = decision.criteria_digest
          AND projection.completion_status = lifecycle.completion_status
          AND projection.projected_run_status = lifecycle.projected_run_status
          AND projection.projected_run_state = lifecycle.projected_run_state
          AND projection.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND projection.action_projection_digest = lifecycle.action_projection_digest
          AND projection.evaluated_at = decision.evaluated_at
          AND json(projection.blockers_json) = json(
              json_extract(lifecycle.payload_json, '$.blockers')
          )
    ) THEN RAISE(ABORT, 'completion projection repair is not required') END;

    SELECT CASE WHEN NEW.outcome = 'already_current' AND NOT EXISTS (
        SELECT 1
        FROM workflow_completion_projections projection
        JOIN workflow_completion_lifecycle_events lifecycle
          ON lifecycle.event_id = NEW.lifecycle_event_id
        JOIN workflow_completion_decisions decision
          ON decision.decision_id = NEW.decision_id
        WHERE projection.tenant_id = NEW.tenant_id
          AND projection.workflow_id = NEW.workflow_id
          AND projection.graph_revision = lifecycle.graph_revision
          AND projection.decision_id = NEW.decision_id
          AND projection.decision_digest = NEW.decision_digest
          AND projection.criteria_digest = decision.criteria_digest
          AND projection.completion_status = lifecycle.completion_status
          AND projection.projected_run_status = lifecycle.projected_run_status
          AND projection.projected_run_state = lifecycle.projected_run_state
          AND projection.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND projection.action_projection_digest = lifecycle.action_projection_digest
          AND projection.evaluated_at = decision.evaluated_at
          AND json(projection.blockers_json) = json(
              json_extract(lifecycle.payload_json, '$.blockers')
          )
    ) THEN RAISE(ABORT, 'completion projection is not current') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM agent_events event
        WHERE event.id = 'completion-projection-repair:' || NEW.command_id
          AND event.agent_run_id = NEW.workflow_id
          AND event.event_type = 'completion_projection_repaired'
          AND event.status = NEW.outcome
          AND event.principal_type = NEW.principal_type
          AND event.principal_id = NEW.principal_id
          AND event.is_policy_event = 1
          AND event.created_at = NEW.completed_at
          AND json_extract(event.anchors_json, '$.command_id') = NEW.command_id
          AND json_extract(event.anchors_json, '$.idempotency_key') = NEW.idempotency_key
          AND json_extract(event.anchors_json, '$.request_hash') = NEW.request_hash
          AND json_extract(event.anchors_json, '$.lifecycle_event_id') = NEW.lifecycle_event_id
          AND json_extract(event.anchors_json, '$.decision_id') = NEW.decision_id
          AND json_extract(event.anchors_json, '$.decision_digest') = NEW.decision_digest
          AND CAST(json_extract(
              event.anchors_json, '$.authoritative_event_sequence'
          ) AS INTEGER) = NEW.authoritative_event_sequence
          AND (
              (
                  NEW.prior_projection_version IS NULL
                  AND json_type(
                      event.anchors_json, '$.prior_projection_version'
                  ) = 'null'
              )
              OR CAST(json_extract(
                  event.anchors_json, '$.prior_projection_version'
              ) AS INTEGER) = NEW.prior_projection_version
          )
          AND CAST(json_extract(
              event.anchors_json, '$.resulting_projection_version'
          ) AS INTEGER) = NEW.resulting_projection_version
    ) THEN RAISE(ABORT, 'completion projection repair audit is invalid') END;
END;

-- Every compatibility projection must match the latest immutable lifecycle
-- event and cursor. Repair may restore the same or an older projection cursor
-- only when its immutable receipt has already been inserted in the transaction.
DROP TRIGGER IF EXISTS workflow_completion_projection_decision_guard_insert;
DROP TRIGGER IF EXISTS workflow_completion_projection_decision_guard_update;

CREATE TRIGGER workflow_completion_projection_decision_guard_insert
BEFORE INSERT ON workflow_completion_projections
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_decisions decision
        JOIN workflow_completion_lifecycle_events lifecycle
          ON lifecycle.decision_id = decision.decision_id
         AND lifecycle.decision_digest = decision.decision_digest
        JOIN workflow_completion_event_cursors cursor
          ON cursor.tenant_id = lifecycle.tenant_id
         AND cursor.workflow_id = lifecycle.workflow_id
         AND cursor.current_sequence = lifecycle.authoritative_event_sequence
        WHERE decision.decision_id = NEW.decision_id
          AND decision.decision_digest = NEW.decision_digest
          AND decision.criteria_digest = NEW.criteria_digest
          AND decision.tenant_id = NEW.tenant_id
          AND decision.workflow_id = NEW.workflow_id
          AND decision.graph_revision = NEW.graph_revision
          AND decision.status = NEW.completion_status
          AND decision.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND decision.evaluated_at = NEW.evaluated_at
          AND lifecycle.graph_revision = NEW.graph_revision
          AND lifecycle.completion_status = NEW.completion_status
          AND lifecycle.projected_run_status = NEW.projected_run_status
          AND lifecycle.projected_run_state = NEW.projected_run_state
          AND lifecycle.action_projection_digest = NEW.action_projection_digest
          AND json(NEW.blockers_json) = json(
              json_extract(lifecycle.payload_json, '$.blockers')
          )
    ) THEN RAISE(ABORT, 'completion projection lifecycle binding is invalid') END;
END;

CREATE TRIGGER workflow_completion_projection_decision_guard_update
BEFORE UPDATE ON workflow_completion_projections
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_decisions decision
        JOIN workflow_completion_lifecycle_events lifecycle
          ON lifecycle.decision_id = decision.decision_id
         AND lifecycle.decision_digest = decision.decision_digest
        JOIN workflow_completion_event_cursors cursor
          ON cursor.tenant_id = lifecycle.tenant_id
         AND cursor.workflow_id = lifecycle.workflow_id
         AND cursor.current_sequence = lifecycle.authoritative_event_sequence
        WHERE decision.decision_id = NEW.decision_id
          AND decision.decision_digest = NEW.decision_digest
          AND decision.criteria_digest = NEW.criteria_digest
          AND decision.tenant_id = NEW.tenant_id
          AND decision.workflow_id = NEW.workflow_id
          AND decision.graph_revision = NEW.graph_revision
          AND decision.status = NEW.completion_status
          AND decision.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND decision.evaluated_at = NEW.evaluated_at
          AND lifecycle.graph_revision = NEW.graph_revision
          AND lifecycle.completion_status = NEW.completion_status
          AND lifecycle.projected_run_status = NEW.projected_run_status
          AND lifecycle.projected_run_state = NEW.projected_run_state
          AND lifecycle.action_projection_digest = NEW.action_projection_digest
          AND json(NEW.blockers_json) = json(
              json_extract(lifecycle.payload_json, '$.blockers')
          )
    ) THEN RAISE(ABORT, 'completion projection lifecycle binding is invalid') END;
    SELECT CASE WHEN (
        NEW.authoritative_event_sequence <= OLD.authoritative_event_sequence
        OR NEW.evaluated_at < OLD.evaluated_at
    )
      AND NOT EXISTS (
        SELECT 1
        FROM workflow_completion_projection_repairs repair
        JOIN workflow_completion_lifecycle_events lifecycle
          ON lifecycle.event_id = repair.lifecycle_event_id
        WHERE repair.tenant_id = NEW.tenant_id
          AND repair.workflow_id = NEW.workflow_id
          AND repair.outcome = 'repaired'
          AND repair.decision_id = NEW.decision_id
          AND repair.decision_digest = NEW.decision_digest
          AND repair.authoritative_event_sequence = NEW.authoritative_event_sequence
          AND repair.resulting_projection_version = NEW.projection_version
          AND NEW.projection_version = OLD.projection_version + 1
          AND lifecycle.tenant_id = NEW.tenant_id
          AND lifecycle.workflow_id = NEW.workflow_id
          AND lifecycle.decision_id = repair.decision_id
          AND lifecycle.decision_digest = repair.decision_digest
          AND lifecycle.authoritative_event_sequence = repair.authoritative_event_sequence
          AND lifecycle.graph_revision = NEW.graph_revision
          AND lifecycle.completion_status = NEW.completion_status
          AND lifecycle.projected_run_status = NEW.projected_run_status
          AND lifecycle.projected_run_state = NEW.projected_run_state
          AND lifecycle.action_projection_digest = NEW.action_projection_digest
      )
    THEN RAISE(ABORT, 'completion projection cannot move backward') END;
END;
