CREATE TABLE IF NOT EXISTS agent_registry_tool_ownership (
    tool_id TEXT PRIMARY KEY,
    owner_principal_id TEXT NOT NULL,
    steward_team TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'registry_default',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_tool_ownership_steward
ON agent_registry_tool_ownership(steward_team, tool_id);
