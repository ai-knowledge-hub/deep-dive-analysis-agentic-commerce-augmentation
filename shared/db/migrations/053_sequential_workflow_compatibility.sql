-- Slice 7a: immutable revision-1 shadow for the current sequential runtime.
-- These records are compatibility evidence only. agent_runs/agent_actions remain
-- the execution authority until the durable workflow kernel is selected.

CREATE TABLE IF NOT EXISTS workflow_compatibility_runs (
    workflow_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_agent_run_id TEXT NOT NULL UNIQUE,
    root_workflow_id TEXT NOT NULL,
    parent_workflow_id TEXT,
    objective_json TEXT NOT NULL CHECK (json_valid(objective_json)),
    objective_hash TEXT NOT NULL,
    initial_status TEXT NOT NULL,
    initial_state TEXT NOT NULL,
    active_revision INTEGER NOT NULL CHECK (active_revision = 1),
    principal_type TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    authority_json TEXT NOT NULL CHECK (json_valid(authority_json)),
    authority_hash TEXT NOT NULL,
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    agent_profile_id TEXT,
    harness_id TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    registry_version TEXT NOT NULL,
    registry_fingerprint TEXT NOT NULL,
    idempotency_key TEXT,
    request_hash TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    source_created_at TEXT NOT NULL,
    structural_digest TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_compatibility_run_scope
    ON workflow_compatibility_runs(tenant_id, workflow_id);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_runs_no_replace
BEFORE INSERT ON workflow_compatibility_runs
WHEN EXISTS (
    SELECT 1 FROM workflow_compatibility_runs
    WHERE workflow_id = NEW.workflow_id
       OR source_agent_run_id = NEW.source_agent_run_id
)
BEGIN
    SELECT RAISE(ABORT, 'workflow compatibility run snapshot already exists');
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_run_source_guard
BEFORE INSERT ON workflow_compatibility_runs
BEGIN
    SELECT CASE WHEN NEW.workflow_id <> NEW.source_agent_run_id
      OR NOT EXISTS (
        SELECT 1 FROM agent_runs run
        WHERE run.id = NEW.source_agent_run_id
          AND run.client_id = NEW.tenant_id
          AND run.principal_type = NEW.principal_type
          AND run.principal_id = NEW.principal_id
          AND run.registry_version = NEW.registry_version
          AND run.registry_fingerprint = NEW.registry_fingerprint
          AND run.trace_id = NEW.trace_id
      )
      OR (
        NEW.root_workflow_id <> NEW.workflow_id
        AND NOT EXISTS (
          SELECT 1 FROM agent_runs root
          WHERE root.id = NEW.root_workflow_id
            AND root.client_id = NEW.tenant_id
        )
      )
      OR (
        NEW.parent_workflow_id IS NOT NULL
        AND NOT EXISTS (
          SELECT 1 FROM agent_runs parent
          WHERE parent.id = NEW.parent_workflow_id
            AND parent.client_id = NEW.tenant_id
        )
      )
    THEN RAISE(ABORT, 'workflow compatibility source run is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_runs_no_update
BEFORE UPDATE ON workflow_compatibility_runs
BEGIN
    SELECT RAISE(ABORT, 'workflow compatibility run snapshot is immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_runs_no_delete
BEFORE DELETE ON workflow_compatibility_runs
BEGIN
    SELECT RAISE(ABORT, 'workflow compatibility run snapshot is immutable');
END;

CREATE TABLE IF NOT EXISTS workflow_compatibility_revisions (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision = 1),
    parent_revision INTEGER,
    reason TEXT NOT NULL CHECK (reason = 'initial_plan'),
    planner_contract_version TEXT NOT NULL,
    graph_hash TEXT NOT NULL,
    created_by_principal_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, workflow_id, revision),
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES workflow_compatibility_runs(tenant_id, workflow_id)
        ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_revisions_no_replace
BEFORE INSERT ON workflow_compatibility_revisions
WHEN EXISTS (
    SELECT 1 FROM workflow_compatibility_revisions
    WHERE tenant_id = NEW.tenant_id
      AND workflow_id = NEW.workflow_id
      AND revision = NEW.revision
)
BEGIN
    SELECT RAISE(ABORT, 'workflow revision already exists');
END;

CREATE TABLE IF NOT EXISTS workflow_compatibility_tasks (
    task_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    source_action_id TEXT NOT NULL UNIQUE,
    introduced_in_revision INTEGER NOT NULL CHECK (introduced_in_revision = 1),
    task_key TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    task_type TEXT NOT NULL,
    capability_version TEXT,
    initial_status TEXT NOT NULL,
    effect_class TEXT NOT NULL,
    skill_id TEXT,
    skill_version TEXT,
    tool_id TEXT,
    tool_version TEXT,
    input_json TEXT NOT NULL CHECK (json_valid(input_json)),
    input_hash TEXT NOT NULL,
    result_schema_id TEXT NOT NULL,
    result_schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, workflow_id, introduced_in_revision)
        REFERENCES workflow_compatibility_revisions(tenant_id, workflow_id, revision)
        ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, task_key),
    UNIQUE (tenant_id, workflow_id, sequence),
    UNIQUE (tenant_id, workflow_id, task_id)
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_tasks_no_replace
BEFORE INSERT ON workflow_compatibility_tasks
WHEN EXISTS (
    SELECT 1 FROM workflow_compatibility_tasks
    WHERE task_id = NEW.task_id OR source_action_id = NEW.source_action_id
)
BEGIN
    SELECT RAISE(ABORT, 'workflow task already exists');
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_task_source_guard
BEFORE INSERT ON workflow_compatibility_tasks
BEGIN
    SELECT CASE WHEN NEW.task_id <> NEW.source_action_id
      OR NOT EXISTS (
        SELECT 1
        FROM agent_actions action
        JOIN agent_runs run ON run.id = action.agent_run_id
        WHERE action.id = NEW.source_action_id
          AND action.agent_run_id = NEW.workflow_id
          AND action.sequence = NEW.sequence
          AND run.client_id = NEW.tenant_id
      )
    THEN RAISE(ABORT, 'workflow compatibility source action is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_compatibility_revision_tasks (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision = 1),
    task_id TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition = 'active'),
    reason TEXT NOT NULL CHECK (reason = 'initial_plan'),
    PRIMARY KEY (tenant_id, workflow_id, revision, task_id),
    FOREIGN KEY (tenant_id, workflow_id, revision)
        REFERENCES workflow_compatibility_revisions(tenant_id, workflow_id, revision)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id, task_id)
        REFERENCES workflow_compatibility_tasks(
            tenant_id, workflow_id, task_id
        ) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_membership_no_replace
BEFORE INSERT ON workflow_compatibility_revision_tasks
WHEN EXISTS (
    SELECT 1 FROM workflow_compatibility_revision_tasks
    WHERE tenant_id = NEW.tenant_id
      AND workflow_id = NEW.workflow_id
      AND revision = NEW.revision
      AND task_id = NEW.task_id
)
BEGIN
    SELECT RAISE(ABORT, 'workflow revision membership already exists');
END;

CREATE TABLE IF NOT EXISTS workflow_compatibility_edges (
    edge_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision = 1),
    from_task_id TEXT NOT NULL,
    to_task_id TEXT NOT NULL,
    join_policy TEXT NOT NULL CHECK (join_policy = 'all'),
    FOREIGN KEY (tenant_id, workflow_id, revision)
        REFERENCES workflow_compatibility_revisions(tenant_id, workflow_id, revision)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id, revision, from_task_id)
        REFERENCES workflow_compatibility_revision_tasks(
            tenant_id, workflow_id, revision, task_id
        ) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, workflow_id, revision, to_task_id)
        REFERENCES workflow_compatibility_revision_tasks(
            tenant_id, workflow_id, revision, task_id
        ) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, revision, from_task_id, to_task_id),
    CHECK (from_task_id <> to_task_id)
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_edges_no_replace
BEFORE INSERT ON workflow_compatibility_edges
WHEN EXISTS (
    SELECT 1 FROM workflow_compatibility_edges
    WHERE edge_id = NEW.edge_id
       OR (
         tenant_id = NEW.tenant_id
         AND workflow_id = NEW.workflow_id
         AND revision = NEW.revision
         AND from_task_id = NEW.from_task_id
         AND to_task_id = NEW.to_task_id
       )
)
BEGIN
    SELECT RAISE(ABORT, 'workflow edge already exists');
END;

CREATE TABLE IF NOT EXISTS workflow_compatibility_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    source_event_id TEXT NOT NULL UNIQUE,
    source_row_order INTEGER NOT NULL CHECK (source_row_order >= 0),
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL CHECK (event_version = '1.0'),
    entity_type TEXT NOT NULL CHECK (entity_type IN ('workflow', 'task')),
    entity_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    event_index INTEGER NOT NULL CHECK (event_index >= 0),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    payload_hash TEXT NOT NULL,
    causation_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES workflow_compatibility_runs(tenant_id, workflow_id)
        ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, sequence),
    UNIQUE (tenant_id, workflow_id, command_id, event_index)
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_event_source_guard
BEFORE INSERT ON workflow_compatibility_events
BEGIN
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM workflow_compatibility_events stored
        WHERE stored.event_id = NEW.event_id
           OR stored.source_event_id = NEW.source_event_id
    ) THEN RAISE(ABORT, 'workflow compatibility event already exists') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM agent_events event
        JOIN agent_runs run ON run.id = event.agent_run_id
        LEFT JOIN agent_actions action ON action.id = event.action_id
        WHERE event.id = NEW.source_event_id
          AND event.agent_run_id = NEW.workflow_id
          AND run.client_id = NEW.tenant_id
          AND (
            event.action_id IS NULL
            OR action.agent_run_id = event.agent_run_id
          )
          AND NEW.event_id = 'workflow-event:' || event.id
          AND NEW.source_row_order = event.rowid
          AND NEW.event_type = 'compatibility.agent.' || event.event_type
          AND NEW.entity_type = CASE
                WHEN event.action_id IS NULL THEN 'workflow' ELSE 'task' END
          AND NEW.entity_id = COALESCE(event.action_id, event.agent_run_id)
          AND NEW.principal_id = COALESCE(event.principal_id, run.principal_id)
          AND NEW.command_id = 'compatibility-import:' || event.agent_run_id
          AND NEW.event_index = event.rowid
          AND NEW.payload_json = workflow_compatibility_event_payload(
                event.id, event.sequence, event.status, event.capability_name,
                event.capability_version, event.tool_id, event.skill_id,
                event.effect_class, event.anchors_json, event.note_text,
                event.is_policy_event
          )
          AND NEW.payload_hash = workflow_sha256(NEW.payload_json)
          AND NEW.causation_id = event.id
          AND NEW.correlation_id = COALESCE(event.trace_id, run.trace_id)
          AND NEW.trace_id = COALESCE(event.trace_id, run.trace_id)
          AND NEW.occurred_at = event.created_at
    ) THEN RAISE(ABORT, 'workflow compatibility source event is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_compatibility_projection_status (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    projection_state TEXT NOT NULL CHECK (
        projection_state IN ('current', 'drifted', 'failed')
    ),
    structural_digest TEXT,
    source_action_count INTEGER NOT NULL DEFAULT 0 CHECK (source_action_count >= 0),
    projected_task_count INTEGER NOT NULL DEFAULT 0 CHECK (projected_task_count >= 0),
    source_event_count INTEGER NOT NULL DEFAULT 0 CHECK (source_event_count >= 0),
    projected_event_count INTEGER NOT NULL DEFAULT 0 CHECK (projected_event_count >= 0),
    error_code TEXT,
    checked_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, workflow_id)
);

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_status_source_guard
BEFORE INSERT ON workflow_compatibility_projection_status
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM agent_runs run
        WHERE run.id = NEW.workflow_id AND run.client_id = NEW.tenant_id
    ) THEN RAISE(ABORT, 'workflow compatibility status source is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_status_update_scope_guard
BEFORE UPDATE ON workflow_compatibility_projection_status
BEGIN
    SELECT CASE WHEN NEW.workflow_id <> OLD.workflow_id
      OR NEW.tenant_id <> OLD.tenant_id
      OR NOT EXISTS (
        SELECT 1 FROM agent_runs run
        WHERE run.id = NEW.workflow_id AND run.client_id = NEW.tenant_id
      )
    THEN RAISE(ABORT, 'workflow compatibility status source is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_compatibility_revisions_no_update
BEFORE UPDATE ON workflow_compatibility_revisions
BEGIN SELECT RAISE(ABORT, 'workflow revision is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_revisions_no_delete
BEFORE DELETE ON workflow_compatibility_revisions
BEGIN SELECT RAISE(ABORT, 'workflow revision is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_tasks_no_update
BEFORE UPDATE ON workflow_compatibility_tasks
BEGIN SELECT RAISE(ABORT, 'workflow task identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_tasks_no_delete
BEFORE DELETE ON workflow_compatibility_tasks
BEGIN SELECT RAISE(ABORT, 'workflow task identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_revision_tasks_no_update
BEFORE UPDATE ON workflow_compatibility_revision_tasks
BEGIN SELECT RAISE(ABORT, 'workflow revision membership is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_revision_tasks_no_delete
BEFORE DELETE ON workflow_compatibility_revision_tasks
BEGIN SELECT RAISE(ABORT, 'workflow revision membership is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_edges_no_update
BEFORE UPDATE ON workflow_compatibility_edges
BEGIN SELECT RAISE(ABORT, 'workflow edge is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_edges_no_delete
BEFORE DELETE ON workflow_compatibility_edges
BEGIN SELECT RAISE(ABORT, 'workflow edge is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_events_no_update
BEFORE UPDATE ON workflow_compatibility_events
BEGIN SELECT RAISE(ABORT, 'workflow event is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_events_no_delete
BEFORE DELETE ON workflow_compatibility_events
BEGIN SELECT RAISE(ABORT, 'workflow event is immutable'); END;

CREATE VIEW IF NOT EXISTS workflow_sequential_run_projection AS
SELECT
    shadow.tenant_id,
    shadow.workflow_id,
    shadow.active_revision,
    run.status,
    run.state,
    run.principal_type,
    run.principal_id,
    run.registry_version,
    run.registry_fingerprint,
    shadow.structural_digest
FROM workflow_compatibility_runs shadow
JOIN agent_runs run
  ON run.id = shadow.source_agent_run_id
 AND run.client_id = shadow.tenant_id;

CREATE VIEW IF NOT EXISTS workflow_sequential_task_projection AS
SELECT
    task.tenant_id,
    task.workflow_id,
    task.task_id,
    task.sequence,
    task.task_type,
    task.capability_version,
    task.initial_status,
    action.status,
    action.outputs_hash,
    action.error_text
FROM workflow_compatibility_tasks task
JOIN agent_actions action
  ON action.id = task.source_action_id
 AND action.agent_run_id = task.workflow_id;
