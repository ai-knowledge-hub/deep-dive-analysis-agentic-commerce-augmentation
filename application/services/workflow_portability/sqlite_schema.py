"""Versioned SQLite schema for the isolated portability benchmark."""

from application.services.workflow_portability.sqlite_durable_history import (
    DURABLE_HISTORY_SCHEMA,
)
from application.services.workflow_portability.sqlite_graph_definition import (
    GRAPH_DEFINITION_SCHEMA,
)
from domain.workflow.portability import PORTABILITY_CONTRACT_VERSION


SQLITE_SCHEMA_VERSION = 5
SQLITE_SCHEMA = f"""
CREATE TABLE portability_benchmark_schema (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (
        schema_version = {SQLITE_SCHEMA_VERSION}
    )
);

INSERT INTO portability_benchmark_schema (singleton, schema_version)
VALUES (1, {SQLITE_SCHEMA_VERSION});

CREATE TABLE portability_benchmark_workflows (
    tenant_id TEXT NOT NULL CHECK (length(tenant_id) > 0),
    workflow_id TEXT NOT NULL CHECK (length(workflow_id) > 0),
    graph_revision INTEGER NOT NULL CHECK (graph_revision >= 1),
    contract_version TEXT NOT NULL CHECK (contract_version = '{PORTABILITY_CONTRACT_VERSION}'),
    PRIMARY KEY (tenant_id, workflow_id),
    UNIQUE (tenant_id, workflow_id, graph_revision)
);

{GRAPH_DEFINITION_SCHEMA}

{DURABLE_HISTORY_SCHEMA}

CREATE TABLE portability_benchmark_commands (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL,
    command_id TEXT NOT NULL CHECK (length(command_id) > 0),
    operation TEXT NOT NULL,
    task_id TEXT,
    attempt_id TEXT,
    worker_id TEXT,
    fencing_token INTEGER,
    lease_expires_at_tick INTEGER,
    effect_id TEXT,
    payload_hash TEXT,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    PRIMARY KEY (tenant_id, workflow_id, command_id),
    FOREIGN KEY (tenant_id, workflow_id, graph_revision)
        REFERENCES portability_benchmark_workflows
            (tenant_id, workflow_id, graph_revision)
);

CREATE UNIQUE INDEX portability_benchmark_effect_command
ON portability_benchmark_commands (tenant_id, workflow_id, effect_id)
WHERE effect_id IS NOT NULL;

CREATE TABLE portability_benchmark_events (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    event_type TEXT NOT NULL CHECK (length(event_type) > 0),
    command_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, workflow_id, sequence),
    UNIQUE (tenant_id, workflow_id, command_id),
    FOREIGN KEY (tenant_id, workflow_id, command_id)
        REFERENCES portability_benchmark_commands
            (tenant_id, workflow_id, command_id)
);

CREATE TABLE portability_benchmark_command_receipts (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    first_event_sequence INTEGER NOT NULL CHECK (first_event_sequence >= 0),
    last_event_sequence INTEGER NOT NULL CHECK (
        last_event_sequence = first_event_sequence
    ),
    PRIMARY KEY (tenant_id, workflow_id, command_id),
    UNIQUE (tenant_id, workflow_id, first_event_sequence),
    FOREIGN KEY (tenant_id, workflow_id, command_id)
        REFERENCES portability_benchmark_commands
            (tenant_id, workflow_id, command_id),
    FOREIGN KEY (tenant_id, workflow_id, first_event_sequence)
        REFERENCES portability_benchmark_events
            (tenant_id, workflow_id, sequence)
);

CREATE TABLE portability_benchmark_effect_receipts (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    effect_id TEXT NOT NULL CHECK (length(effect_id) > 0),
    command_id TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    graph_revision INTEGER NOT NULL CHECK (graph_revision >= 1),
    task_id TEXT NOT NULL CHECK (length(task_id) > 0),
    attempt_id TEXT NOT NULL CHECK (length(attempt_id) > 0),
    worker_id TEXT NOT NULL CHECK (length(worker_id) > 0),
    fencing_token INTEGER NOT NULL CHECK (fencing_token >= 1),
    payload_hash TEXT NOT NULL CHECK (length(payload_hash) = 64),
    provider_receipt_id TEXT NOT NULL CHECK (length(provider_receipt_id) > 0),
    PRIMARY KEY (tenant_id, workflow_id, effect_id),
    UNIQUE (tenant_id, workflow_id, command_id),
    UNIQUE (tenant_id, workflow_id, provider_receipt_id),
    FOREIGN KEY (tenant_id, workflow_id, command_id)
        REFERENCES portability_benchmark_commands
            (tenant_id, workflow_id, command_id)
);

CREATE TABLE portability_benchmark_checkpoints (
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    graph_revision INTEGER NOT NULL,
    event_sequence INTEGER NOT NULL,
    history_hash TEXT NOT NULL CHECK (length(history_hash) = 64),
    committed_receipt_ids_json TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    checkpoint_hash TEXT NOT NULL CHECK (length(checkpoint_hash) = 64),
    PRIMARY KEY (tenant_id, workflow_id, history_hash),
    FOREIGN KEY (tenant_id, workflow_id, graph_revision)
        REFERENCES portability_benchmark_workflows
            (tenant_id, workflow_id, graph_revision)
);

CREATE TRIGGER portability_benchmark_event_sequence_guard
BEFORE INSERT ON portability_benchmark_events
BEGIN
    SELECT CASE WHEN NEW.sequence != COALESCE((
        SELECT MAX(sequence) + 1
        FROM portability_benchmark_events
        WHERE tenant_id = NEW.tenant_id AND workflow_id = NEW.workflow_id
    ), 0) THEN RAISE(ABORT, 'portability event sequence must be gap-free') END;
END;

CREATE TRIGGER portability_benchmark_command_receipt_binding
BEFORE INSERT ON portability_benchmark_command_receipts
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM portability_benchmark_events event
        WHERE event.tenant_id = NEW.tenant_id
          AND event.workflow_id = NEW.workflow_id
          AND event.sequence = NEW.first_event_sequence
          AND event.command_id = NEW.command_id
    ) THEN RAISE(ABORT, 'portability command receipt must bind its event') END;
END;

CREATE TRIGGER portability_benchmark_effect_receipt_binding
BEFORE INSERT ON portability_benchmark_effect_receipts
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM portability_benchmark_commands command
        WHERE command.tenant_id = NEW.tenant_id
          AND command.workflow_id = NEW.workflow_id
          AND command.command_id = NEW.command_id
          AND command.operation = 'commit_effect'
          AND command.request_hash = NEW.request_hash
          AND command.graph_revision = NEW.graph_revision
          AND command.task_id = NEW.task_id
          AND command.attempt_id = NEW.attempt_id
          AND command.worker_id = NEW.worker_id
          AND command.fencing_token = NEW.fencing_token
          AND command.effect_id = NEW.effect_id
          AND command.payload_hash = NEW.payload_hash
    ) THEN RAISE(ABORT, 'portability effect receipt binding mismatch') END;
END;
"""

__all__ = ["SQLITE_SCHEMA", "SQLITE_SCHEMA_VERSION"]
