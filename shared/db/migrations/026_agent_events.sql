CREATE TABLE IF NOT EXISTS agent_events (
    id TEXT PRIMARY KEY,
    agent_run_id TEXT NOT NULL,
    action_id TEXT,
    sequence INTEGER NOT NULL DEFAULT 0,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    capability_name TEXT,
    capability_version TEXT,
    note_text TEXT,
    is_policy_event INTEGER NOT NULL DEFAULT 0,
    anchors_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(agent_run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(action_id) REFERENCES agent_actions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_events_run_created
    ON agent_events(agent_run_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_agent_events_run_event_type
    ON agent_events(agent_run_id, event_type);
