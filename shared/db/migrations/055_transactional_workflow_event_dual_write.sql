-- Slice 7c: project new authoritative agent events into the immutable
-- sequential-workflow compatibility stream in the source writer's transaction.
--
-- Runs without a compatibility shadow are pre-Slice-7c/legacy candidates.  The
-- bounded reconciler continues to create and backfill those shadows.  Once a
-- shadow exists, projection is mandatory: any conflict aborts the source write.

ALTER TABLE agent_runs
ADD COLUMN workflow_event_projection_required INTEGER NOT NULL DEFAULT 0
    CHECK (workflow_event_projection_required IN (0, 1));

-- The projection fence is monotonic.  A compatibility shadow also makes the
-- fence mandatory, even if an inconsistent row was introduced before this
-- trigger existed.
CREATE TRIGGER IF NOT EXISTS workflow_event_projection_fence_no_downgrade
BEFORE UPDATE OF workflow_event_projection_required ON agent_runs
WHEN NEW.workflow_event_projection_required = 0
  AND (
    OLD.workflow_event_projection_required = 1
    OR EXISTS (
        SELECT 1 FROM workflow_compatibility_runs shadow
        WHERE shadow.source_agent_run_id IN (OLD.id, NEW.id)
    )
  )
BEGIN
    SELECT RAISE(ABORT, 'workflow event projection fence is permanent');
END;

-- The immutable shadow must never outlive its authoritative source run.  The
-- fence also protects current-writer runs during the interval before their
-- shadow is established.
CREATE TRIGGER IF NOT EXISTS projected_agent_runs_no_delete
BEFORE DELETE ON agent_runs
WHEN OLD.workflow_event_projection_required = 1
  OR EXISTS (
    SELECT 1 FROM workflow_compatibility_runs shadow
    WHERE shadow.source_agent_run_id = OLD.id
  )
BEGIN
    SELECT RAISE(ABORT, 'projected agent run is immutable');
END;

-- The shadow pins both the source identity and its tenant scope.  Checking the
-- new identifier also prevents an unfenced row from being renamed onto an
-- identity already retained by an immutable shadow.
CREATE TRIGGER IF NOT EXISTS projected_agent_runs_no_identity_update
BEFORE UPDATE OF id, client_id ON agent_runs
WHEN (NEW.id IS NOT OLD.id OR NEW.client_id IS NOT OLD.client_id)
  AND (
    OLD.workflow_event_projection_required = 1
    OR EXISTS (
        SELECT 1 FROM workflow_compatibility_runs shadow
        WHERE shadow.source_agent_run_id IN (OLD.id, NEW.id)
    )
  )
BEGIN
    SELECT RAISE(
        ABORT,
        'projected agent run identity and tenant are immutable'
    );
END;

-- SQLite REPLACE may bypass DELETE triggers when recursive triggers are off,
-- so reject reuse of a protected run identity before replacement can remove
-- the source row and cascade-delete its actions.
CREATE TRIGGER IF NOT EXISTS projected_agent_runs_no_replace
BEFORE INSERT ON agent_runs
WHEN EXISTS (
    SELECT 1 FROM workflow_compatibility_runs shadow
    WHERE shadow.source_agent_run_id = NEW.id
)
OR EXISTS (
    SELECT 1 FROM agent_runs existing
    WHERE existing.id = NEW.id
      AND existing.workflow_event_projection_required = 1
)
BEGIN
    SELECT RAISE(ABORT, 'projected agent run identity already exists');
END;

-- A current writer marks a new run before committing it. A legacy writer leaves
-- the default at zero, so rollback deployments remain operational and their
-- runs remain bounded reconciliation candidates.
CREATE TRIGGER IF NOT EXISTS agent_events_require_workflow_compatibility_shadow
BEFORE INSERT ON agent_events
WHEN EXISTS (
    SELECT 1 FROM agent_runs run
    WHERE run.id = NEW.agent_run_id
      AND run.workflow_event_projection_required = 1
)
AND NOT EXISTS (
    SELECT 1 FROM workflow_compatibility_runs shadow
    WHERE shadow.source_agent_run_id = NEW.agent_run_id
)
BEGIN
    SELECT RAISE(ABORT, 'workflow compatibility shadow is required');
END;

-- Once a legacy run is reconciled, every subsequent event must use dual-write.
CREATE TRIGGER IF NOT EXISTS workflow_compatibility_run_enables_event_dual_write
AFTER INSERT ON workflow_compatibility_runs
BEGIN
    UPDATE agent_runs
    SET workflow_event_projection_required = 1
    WHERE id = NEW.source_agent_run_id;
END;

-- Once dual-write is required, the source identity/content is append-only too.
-- This prevents an orphan or a coordinated source/shadow rewrite from being
-- manufactured after the atomic insert has committed.
CREATE TRIGGER IF NOT EXISTS projected_agent_events_no_update
BEFORE UPDATE ON agent_events
WHEN OLD.event_type <> 'completion_projection_repaired'
  AND NEW.event_type <> 'completion_projection_repaired'
  AND (
    EXISTS (
        SELECT 1 FROM agent_runs run
        WHERE run.id IN (OLD.agent_run_id, NEW.agent_run_id)
          AND run.workflow_event_projection_required = 1
    )
    OR EXISTS (
        SELECT 1 FROM workflow_compatibility_runs shadow
        WHERE shadow.source_agent_run_id IN (OLD.agent_run_id, NEW.agent_run_id)
    )
    OR EXISTS (
        SELECT 1 FROM workflow_compatibility_events projected
        WHERE projected.source_event_id IN (OLD.id, NEW.id)
    )
  )
BEGIN
    SELECT RAISE(ABORT, 'projected agent event is immutable');
END;

CREATE TRIGGER IF NOT EXISTS projected_agent_events_no_delete
BEFORE DELETE ON agent_events
WHEN OLD.event_type <> 'completion_projection_repaired'
  AND (
    EXISTS (
        SELECT 1 FROM agent_runs run
        WHERE run.id = OLD.agent_run_id
          AND run.workflow_event_projection_required = 1
    )
    OR EXISTS (
        SELECT 1 FROM workflow_compatibility_runs shadow
        WHERE shadow.source_agent_run_id = OLD.agent_run_id
    )
    OR EXISTS (
        SELECT 1 FROM workflow_compatibility_events projected
        WHERE projected.source_event_id = OLD.id
    )
  )
BEGIN
    SELECT RAISE(ABORT, 'projected agent event is immutable');
END;

-- SQLite REPLACE may bypass DELETE triggers when recursive triggers are off,
-- so reject identity reuse before the replacement can remove the source row.
CREATE TRIGGER IF NOT EXISTS projected_agent_events_no_replace
BEFORE INSERT ON agent_events
WHEN EXISTS (
    SELECT 1
    FROM agent_events existing
    JOIN agent_runs run ON run.id = existing.agent_run_id
    WHERE existing.id = NEW.id
      AND existing.event_type <> 'completion_projection_repaired'
      AND (
        run.workflow_event_projection_required = 1
        OR EXISTS (
            SELECT 1 FROM workflow_compatibility_runs shadow
            WHERE shadow.source_agent_run_id = existing.agent_run_id
        )
        OR EXISTS (
            SELECT 1 FROM workflow_compatibility_events projected
            WHERE projected.source_event_id = existing.id
        )
      )
)
BEGIN
    SELECT RAISE(ABORT, 'projected agent event identity already exists');
END;

CREATE TRIGGER IF NOT EXISTS agent_events_workflow_compatibility_dual_write
AFTER INSERT ON agent_events
WHEN EXISTS (
    SELECT 1
    FROM workflow_compatibility_runs shadow
    WHERE shadow.source_agent_run_id = NEW.agent_run_id
)
BEGIN
    INSERT INTO workflow_compatibility_events (
        event_id, tenant_id, workflow_id, sequence, source_event_id,
        source_row_order, event_type, event_version, entity_type,
        entity_id, principal_id, command_id, event_index, payload_json,
        payload_hash, causation_id, correlation_id, trace_id,
        occurred_at, recorded_at
    )
    SELECT
        'workflow-event:' || NEW.id,
        run.client_id,
        NEW.agent_run_id,
        COALESCE((
            SELECT MAX(projected.sequence) + 1
            FROM workflow_compatibility_events projected
            WHERE projected.tenant_id = run.client_id
              AND projected.workflow_id = NEW.agent_run_id
        ), 0),
        NEW.id,
        NEW.rowid,
        'compatibility.agent.' || NEW.event_type,
        '1.0',
        CASE WHEN NEW.action_id IS NULL THEN 'workflow' ELSE 'task' END,
        COALESCE(NEW.action_id, NEW.agent_run_id),
        COALESCE(NEW.principal_id, run.principal_id),
        'compatibility-import:' || NEW.agent_run_id,
        NEW.rowid,
        workflow_compatibility_event_payload(
            NEW.id, NEW.sequence, NEW.status, NEW.capability_name,
            NEW.capability_version, NEW.tool_id, NEW.skill_id,
            NEW.effect_class, NEW.anchors_json, NEW.note_text,
            NEW.is_policy_event
        ),
        workflow_sha256(workflow_compatibility_event_payload(
            NEW.id, NEW.sequence, NEW.status, NEW.capability_name,
            NEW.capability_version, NEW.tool_id, NEW.skill_id,
            NEW.effect_class, NEW.anchors_json, NEW.note_text,
            NEW.is_policy_event
        )),
        NEW.id,
        COALESCE(NEW.trace_id, run.trace_id),
        COALESCE(NEW.trace_id, run.trace_id),
        NEW.created_at,
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    FROM agent_runs run
    WHERE run.id = NEW.agent_run_id;

    UPDATE workflow_compatibility_projection_status
    SET source_action_count = (
            SELECT COUNT(*) FROM agent_actions
            WHERE agent_run_id = NEW.agent_run_id
        ),
        projected_task_count = (
            SELECT COUNT(*) FROM workflow_compatibility_revision_tasks
            WHERE tenant_id = workflow_compatibility_projection_status.tenant_id
              AND workflow_id = NEW.agent_run_id
        ),
        source_event_count = (
            SELECT COUNT(*) FROM agent_events
            WHERE agent_run_id = NEW.agent_run_id
        ),
        projected_event_count = (
            SELECT COUNT(*) FROM workflow_compatibility_events
            WHERE tenant_id = workflow_compatibility_projection_status.tenant_id
              AND workflow_id = NEW.agent_run_id
        ),
        projection_state = CASE
            WHEN (
                SELECT COUNT(*) FROM agent_actions
                WHERE agent_run_id = NEW.agent_run_id
            ) = (
                SELECT COUNT(*) FROM workflow_compatibility_revision_tasks
                WHERE tenant_id = workflow_compatibility_projection_status.tenant_id
                  AND workflow_id = NEW.agent_run_id
            )
            AND (
                SELECT COUNT(*) FROM agent_events
                WHERE agent_run_id = NEW.agent_run_id
            ) = (
                SELECT COUNT(*) FROM workflow_compatibility_events
                WHERE tenant_id = workflow_compatibility_projection_status.tenant_id
                  AND workflow_id = NEW.agent_run_id
            )
            THEN 'current'
            ELSE 'drifted'
        END,
        error_code = CASE
            WHEN (
                SELECT COUNT(*) FROM agent_actions
                WHERE agent_run_id = NEW.agent_run_id
            ) = (
                SELECT COUNT(*) FROM workflow_compatibility_revision_tasks
                WHERE tenant_id = workflow_compatibility_projection_status.tenant_id
                  AND workflow_id = NEW.agent_run_id
            )
            AND (
                SELECT COUNT(*) FROM agent_events
                WHERE agent_run_id = NEW.agent_run_id
            ) = (
                SELECT COUNT(*) FROM workflow_compatibility_events
                WHERE tenant_id = workflow_compatibility_projection_status.tenant_id
                  AND workflow_id = NEW.agent_run_id
            )
            THEN NULL
            ELSE 'cardinality_mismatch'
        END,
        checked_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE workflow_id = NEW.agent_run_id;
END;
