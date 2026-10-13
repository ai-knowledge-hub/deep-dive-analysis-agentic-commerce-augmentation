-- Pre-run conversation identity and exact immutable creation decisions.
CREATE TABLE operator_workspaces (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
    tenant_id TEXT NOT NULL REFERENCES clients(id),
    principal_id TEXT NOT NULL,
    run_id TEXT REFERENCES agent_runs(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE operator_run_creation_proposals (
    proposal_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES operator_workspaces(session_id),
    tenant_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    proposal_digest TEXT NOT NULL CHECK(length(proposal_digest) = 64),
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    created_at TEXT NOT NULL
);
CREATE TABLE operator_run_creation_receipts (
    receipt_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES operator_run_creation_proposals(proposal_id),
    session_id TEXT NOT NULL UNIQUE REFERENCES operator_workspaces(session_id),
    run_id TEXT NOT NULL UNIQUE REFERENCES agent_runs(id),
    receipt_digest TEXT NOT NULL CHECK(length(receipt_digest) = 64),
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    created_at TEXT NOT NULL
);
CREATE TRIGGER operator_workspace_identity_immutable BEFORE UPDATE ON operator_workspaces
WHEN NEW.session_id != OLD.session_id OR NEW.tenant_id != OLD.tenant_id
 OR NEW.principal_id != OLD.principal_id OR NEW.created_at != OLD.created_at
 OR (OLD.run_id IS NOT NULL AND NEW.run_id IS NOT OLD.run_id)
BEGIN SELECT RAISE(ABORT, 'workspace binding is immutable'); END;
CREATE TRIGGER operator_workspace_no_delete BEFORE DELETE ON operator_workspaces
BEGIN SELECT RAISE(ABORT, 'workspace identity is durable'); END;
CREATE TRIGGER operator_creation_proposal_no_update BEFORE UPDATE ON operator_run_creation_proposals
BEGIN SELECT RAISE(ABORT, 'creation proposal is immutable'); END;
CREATE TRIGGER operator_creation_proposal_no_delete BEFORE DELETE ON operator_run_creation_proposals
BEGIN SELECT RAISE(ABORT, 'creation proposal is immutable'); END;
CREATE TRIGGER operator_creation_receipt_no_update BEFORE UPDATE ON operator_run_creation_receipts
BEGIN SELECT RAISE(ABORT, 'creation receipt is immutable'); END;
CREATE TRIGGER operator_creation_receipt_no_delete BEFORE DELETE ON operator_run_creation_receipts
BEGIN SELECT RAISE(ABORT, 'creation receipt is immutable'); END;
