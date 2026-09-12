-- Slice 6b: append-only evidence, result, completion authority, and decision ledger.

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_runs_client_workflow
    ON agent_runs(client_id, id);

CREATE TABLE IF NOT EXISTS workflow_outcome_commands (
    command_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    command_type TEXT NOT NULL CHECK (command_type IN (
        'record_evidence',
        'record_task_result',
        'publish_completion_contract',
        'issue_authority_snapshot',
        'record_completion_decision'
    )),
    principal_id TEXT NOT NULL,
    authority_source TEXT NOT NULL,
    authority_version TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    artifact_digest TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    UNIQUE (tenant_id, workflow_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_workflow_outcome_commands_scope
    ON workflow_outcome_commands(tenant_id, workflow_id, completed_at);

CREATE TABLE IF NOT EXISTS workflow_evidence_records (
    evidence_id TEXT PRIMARY KEY,
    evidence_digest TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    task_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    action_id TEXT,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    recorded_at TEXT NOT NULL,
    command_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (command_id)
        REFERENCES workflow_outcome_commands(command_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_workflow_evidence_scope
    ON workflow_evidence_records(
        tenant_id, workflow_id, graph_revision, task_id, attempt_id
    );

CREATE TRIGGER IF NOT EXISTS workflow_evidence_command_guard
BEFORE INSERT ON workflow_evidence_records
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_outcome_commands command
        WHERE command.command_id = NEW.command_id
          AND command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.command_type = 'record_evidence'
          AND command.artifact_type = 'evidence'
          AND command.artifact_id = NEW.evidence_id
          AND command.artifact_digest = NEW.evidence_digest
    ) THEN RAISE(ABORT, 'evidence command binding is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_task_results (
    result_id TEXT PRIMARY KEY,
    result_digest TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    task_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    assignment_id TEXT,
    validation_status TEXT NOT NULL CHECK (
        validation_status IN ('pending', 'accepted', 'rejected')
    ),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    created_at TEXT NOT NULL,
    validated_at TEXT,
    command_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (command_id)
        REFERENCES workflow_outcome_commands(command_id) ON DELETE RESTRICT,
    UNIQUE (result_id, result_digest)
);

CREATE INDEX IF NOT EXISTS idx_workflow_task_results_scope
    ON workflow_task_results(
        tenant_id, workflow_id, graph_revision, task_id, attempt_id
    );

CREATE TRIGGER IF NOT EXISTS workflow_task_result_command_guard
BEFORE INSERT ON workflow_task_results
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_outcome_commands command
        WHERE command.command_id = NEW.command_id
          AND command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.command_type = 'record_task_result'
          AND command.artifact_type = 'task_result'
          AND command.artifact_id = NEW.result_id
          AND command.artifact_digest = NEW.result_digest
    ) THEN RAISE(ABORT, 'task result command binding is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_result_evidence (
    result_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    PRIMARY KEY (result_id, evidence_id),
    FOREIGN KEY (result_id)
        REFERENCES workflow_task_results(result_id) ON DELETE RESTRICT,
    FOREIGN KEY (evidence_id)
        REFERENCES workflow_evidence_records(evidence_id) ON DELETE RESTRICT,
    FOREIGN KEY (evidence_digest)
        REFERENCES workflow_evidence_records(evidence_digest) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_result_evidence_scope_guard
BEFORE INSERT ON workflow_result_evidence
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_task_results result
        JOIN workflow_evidence_records evidence
          ON evidence.evidence_id = NEW.evidence_id
         AND evidence.evidence_digest = NEW.evidence_digest
        WHERE result.result_id = NEW.result_id
          AND result.tenant_id = evidence.tenant_id
          AND result.workflow_id = evidence.workflow_id
          AND result.graph_revision = evidence.graph_revision
          AND result.task_id = evidence.task_id
          AND result.attempt_id = evidence.attempt_id
    ) THEN RAISE(ABORT, 'result evidence scope is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_completion_criteria (
    criteria_digest TEXT PRIMARY KEY,
    criteria_id TEXT NOT NULL,
    criteria_version TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    objective_id TEXT NOT NULL,
    authority_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    created_at TEXT NOT NULL,
    command_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (command_id)
        REFERENCES workflow_outcome_commands(command_id) ON DELETE RESTRICT,
    UNIQUE (
        tenant_id, workflow_id, graph_revision, criteria_id, criteria_version
    )
);

CREATE INDEX IF NOT EXISTS idx_workflow_completion_criteria_scope
    ON workflow_completion_criteria(
        tenant_id, workflow_id, graph_revision, criteria_id, created_at
    );

CREATE TRIGGER IF NOT EXISTS workflow_completion_criteria_command_guard
BEFORE INSERT ON workflow_completion_criteria
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_outcome_commands command
        WHERE command.command_id = NEW.command_id
          AND command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.command_type = 'publish_completion_contract'
          AND command.artifact_type = 'completion_contract'
          AND command.artifact_id = NEW.criteria_id
          AND command.artifact_digest = NEW.criteria_digest
    ) THEN RAISE(ABORT, 'completion criteria command binding is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_completion_task_definitions (
    criteria_digest TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_input_hash TEXT NOT NULL,
    result_schema_id TEXT NOT NULL,
    result_schema_version TEXT NOT NULL,
    result_schema_hash TEXT NOT NULL,
    PRIMARY KEY (criteria_digest, task_id),
    FOREIGN KEY (criteria_digest)
        REFERENCES workflow_completion_criteria(criteria_digest) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS workflow_completion_authority_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    snapshot_digest TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    objective_id TEXT NOT NULL,
    criteria_id TEXT NOT NULL,
    criteria_digest TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    issued_at TEXT NOT NULL,
    command_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (criteria_digest)
        REFERENCES workflow_completion_criteria(criteria_digest) ON DELETE RESTRICT,
    FOREIGN KEY (command_id)
        REFERENCES workflow_outcome_commands(command_id) ON DELETE RESTRICT,
    UNIQUE (snapshot_id, snapshot_digest)
);

CREATE INDEX IF NOT EXISTS idx_workflow_authority_snapshots_scope
    ON workflow_completion_authority_snapshots(
        tenant_id, workflow_id, graph_revision, criteria_id, issued_at
    );

CREATE TRIGGER IF NOT EXISTS workflow_completion_snapshot_command_guard
BEFORE INSERT ON workflow_completion_authority_snapshots
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_outcome_commands command
        WHERE command.command_id = NEW.command_id
          AND command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.command_type = 'issue_authority_snapshot'
          AND command.artifact_type = 'authority_snapshot'
          AND command.artifact_id = NEW.snapshot_id
          AND command.artifact_digest = NEW.snapshot_digest
    ) THEN RAISE(ABORT, 'authority snapshot command binding is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_snapshot_criteria_guard
BEFORE INSERT ON workflow_completion_authority_snapshots
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_completion_criteria criteria
        WHERE criteria.criteria_digest = NEW.criteria_digest
          AND criteria.criteria_id = NEW.criteria_id
          AND criteria.tenant_id = NEW.tenant_id
          AND criteria.workflow_id = NEW.workflow_id
          AND criteria.graph_revision = NEW.graph_revision
          AND criteria.objective_id = NEW.objective_id
    ) THEN RAISE(ABORT, 'authority snapshot criteria scope is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_completion_snapshot_results (
    snapshot_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    result_id TEXT NOT NULL,
    result_digest TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, task_id),
    FOREIGN KEY (snapshot_id)
        REFERENCES workflow_completion_authority_snapshots(snapshot_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (result_id, result_digest)
        REFERENCES workflow_task_results(result_id, result_digest)
        ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_snapshot_result_scope_guard
BEFORE INSERT ON workflow_completion_snapshot_results
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_authority_snapshots snapshot
        JOIN workflow_task_results result
          ON result.result_id = NEW.result_id
         AND result.result_digest = NEW.result_digest
        WHERE snapshot.snapshot_id = NEW.snapshot_id
          AND result.validation_status = 'accepted'
          AND snapshot.tenant_id = result.tenant_id
          AND snapshot.workflow_id = result.workflow_id
          AND snapshot.graph_revision = result.graph_revision
          AND result.task_id = NEW.task_id
    ) THEN RAISE(ABORT, 'snapshot result authority is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_completion_decisions (
    decision_id TEXT PRIMARY KEY,
    decision_digest TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    objective_id TEXT NOT NULL,
    criteria_id TEXT NOT NULL,
    criteria_digest TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    snapshot_digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('complete', 'incomplete')),
    authoritative_event_sequence INTEGER NOT NULL
        CHECK (authoritative_event_sequence >= 0),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    evaluated_at TEXT NOT NULL,
    command_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (tenant_id, workflow_id)
        REFERENCES agent_runs(client_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (criteria_digest)
        REFERENCES workflow_completion_criteria(criteria_digest) ON DELETE RESTRICT,
    FOREIGN KEY (snapshot_id, snapshot_digest)
        REFERENCES workflow_completion_authority_snapshots(
            snapshot_id, snapshot_digest
        ) ON DELETE RESTRICT,
    FOREIGN KEY (command_id)
        REFERENCES workflow_outcome_commands(command_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_workflow_completion_decisions_scope
    ON workflow_completion_decisions(
        tenant_id, workflow_id, graph_revision, evaluated_at
    );

CREATE TRIGGER IF NOT EXISTS workflow_completion_decision_command_guard
BEFORE INSERT ON workflow_completion_decisions
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM workflow_outcome_commands command
        WHERE command.command_id = NEW.command_id
          AND command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.command_type = 'record_completion_decision'
          AND command.artifact_type = 'completion_decision'
          AND command.artifact_id = NEW.decision_id
          AND command.artifact_digest = NEW.decision_digest
    ) THEN RAISE(ABORT, 'completion decision command binding is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_decision_authority_guard
BEFORE INSERT ON workflow_completion_decisions
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_authority_snapshots snapshot
        JOIN workflow_completion_criteria criteria
          ON criteria.criteria_digest = NEW.criteria_digest
        WHERE snapshot.snapshot_id = NEW.snapshot_id
          AND snapshot.snapshot_digest = NEW.snapshot_digest
          AND snapshot.tenant_id = NEW.tenant_id
          AND snapshot.workflow_id = NEW.workflow_id
          AND snapshot.graph_revision = NEW.graph_revision
          AND snapshot.objective_id = NEW.objective_id
          AND snapshot.criteria_id = NEW.criteria_id
          AND snapshot.criteria_digest = NEW.criteria_digest
          AND criteria.tenant_id = NEW.tenant_id
          AND criteria.workflow_id = NEW.workflow_id
          AND criteria.graph_revision = NEW.graph_revision
          AND criteria.objective_id = NEW.objective_id
          AND criteria.criteria_id = NEW.criteria_id
    ) THEN RAISE(ABORT, 'completion decision authority scope is invalid') END;
END;

CREATE TABLE IF NOT EXISTS workflow_completion_decision_results (
    decision_id TEXT NOT NULL,
    result_id TEXT NOT NULL,
    result_digest TEXT NOT NULL,
    PRIMARY KEY (decision_id, result_id),
    FOREIGN KEY (decision_id)
        REFERENCES workflow_completion_decisions(decision_id) ON DELETE RESTRICT,
    FOREIGN KEY (result_id, result_digest)
        REFERENCES workflow_task_results(result_id, result_digest)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS workflow_completion_decision_evidence (
    decision_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    PRIMARY KEY (decision_id, evidence_id),
    FOREIGN KEY (decision_id)
        REFERENCES workflow_completion_decisions(decision_id) ON DELETE RESTRICT,
    FOREIGN KEY (evidence_id)
        REFERENCES workflow_evidence_records(evidence_id) ON DELETE RESTRICT,
    FOREIGN KEY (evidence_digest)
        REFERENCES workflow_evidence_records(evidence_digest) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS workflow_decision_result_scope_guard
BEFORE INSERT ON workflow_completion_decision_results
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_decisions decision
        JOIN workflow_task_results result
          ON result.result_id = NEW.result_id
         AND result.result_digest = NEW.result_digest
        WHERE decision.decision_id = NEW.decision_id
          AND decision.tenant_id = result.tenant_id
          AND decision.workflow_id = result.workflow_id
          AND decision.graph_revision = result.graph_revision
    ) THEN RAISE(ABORT, 'decision result scope is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_decision_evidence_scope_guard
BEFORE INSERT ON workflow_completion_decision_evidence
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM workflow_completion_decisions decision
        JOIN workflow_evidence_records evidence
          ON evidence.evidence_id = NEW.evidence_id
         AND evidence.evidence_digest = NEW.evidence_digest
        WHERE decision.decision_id = NEW.decision_id
          AND decision.tenant_id = evidence.tenant_id
          AND decision.workflow_id = evidence.workflow_id
          AND decision.graph_revision = evidence.graph_revision
    ) THEN RAISE(ABORT, 'decision evidence scope is invalid') END;
END;

CREATE TRIGGER IF NOT EXISTS workflow_outcome_commands_no_update
BEFORE UPDATE ON workflow_outcome_commands
BEGIN
    SELECT RAISE(ABORT, 'workflow outcome command receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_outcome_commands_no_delete
BEFORE DELETE ON workflow_outcome_commands
BEGIN
    SELECT RAISE(ABORT, 'workflow outcome command receipts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_evidence_records_no_update
BEFORE UPDATE ON workflow_evidence_records
BEGIN
    SELECT RAISE(ABORT, 'workflow evidence records are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_evidence_records_no_delete
BEFORE DELETE ON workflow_evidence_records
BEGIN
    SELECT RAISE(ABORT, 'workflow evidence records are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_task_results_no_update
BEFORE UPDATE ON workflow_task_results
BEGIN
    SELECT RAISE(ABORT, 'workflow task results are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_task_results_no_delete
BEFORE DELETE ON workflow_task_results
BEGIN
    SELECT RAISE(ABORT, 'workflow task results are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_result_evidence_no_update
BEFORE UPDATE ON workflow_result_evidence
BEGIN
    SELECT RAISE(ABORT, 'workflow result evidence bindings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_result_evidence_no_delete
BEFORE DELETE ON workflow_result_evidence
BEGIN
    SELECT RAISE(ABORT, 'workflow result evidence bindings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_criteria_no_update
BEFORE UPDATE ON workflow_completion_criteria
BEGIN
    SELECT RAISE(ABORT, 'workflow completion criteria are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_criteria_no_delete
BEFORE DELETE ON workflow_completion_criteria
BEGIN
    SELECT RAISE(ABORT, 'workflow completion criteria are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_task_definitions_no_update
BEFORE UPDATE ON workflow_completion_task_definitions
BEGIN
    SELECT RAISE(ABORT, 'workflow task definitions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_task_definitions_no_delete
BEFORE DELETE ON workflow_completion_task_definitions
BEGIN
    SELECT RAISE(ABORT, 'workflow task definitions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_snapshots_no_update
BEFORE UPDATE ON workflow_completion_authority_snapshots
BEGIN
    SELECT RAISE(ABORT, 'workflow completion authority snapshots are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_snapshots_no_delete
BEFORE DELETE ON workflow_completion_authority_snapshots
BEGIN
    SELECT RAISE(ABORT, 'workflow completion authority snapshots are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_snapshot_results_no_update
BEFORE UPDATE ON workflow_completion_snapshot_results
BEGIN
    SELECT RAISE(ABORT, 'workflow snapshot result bindings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_snapshot_results_no_delete
BEFORE DELETE ON workflow_completion_snapshot_results
BEGIN
    SELECT RAISE(ABORT, 'workflow snapshot result bindings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_decisions_no_update
BEFORE UPDATE ON workflow_completion_decisions
BEGIN
    SELECT RAISE(ABORT, 'workflow completion decisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_decisions_no_delete
BEFORE DELETE ON workflow_completion_decisions
BEGIN
    SELECT RAISE(ABORT, 'workflow completion decisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_decision_results_no_update
BEFORE UPDATE ON workflow_completion_decision_results
BEGIN
    SELECT RAISE(ABORT, 'workflow completion decision inputs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_decision_results_no_delete
BEFORE DELETE ON workflow_completion_decision_results
BEGIN
    SELECT RAISE(ABORT, 'workflow completion decision inputs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_decision_evidence_no_update
BEFORE UPDATE ON workflow_completion_decision_evidence
BEGIN
    SELECT RAISE(ABORT, 'workflow completion decision inputs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS workflow_completion_decision_evidence_no_delete
BEFORE DELETE ON workflow_completion_decision_evidence
BEGIN
    SELECT RAISE(ABORT, 'workflow completion decision inputs are immutable');
END;
