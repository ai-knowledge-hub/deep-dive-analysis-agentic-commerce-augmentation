CREATE TABLE IF NOT EXISTS agent_registry_harness_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    default_run_mode TEXT NOT NULL,
    default_policy_profile_id TEXT NOT NULL,
    allowed_run_modes_json TEXT NOT NULL DEFAULT '[]',
    allowed_policy_profile_ids_json TEXT NOT NULL DEFAULT '[]',
    planner_mode TEXT,
    retry_strategy TEXT,
    fallback_order_json TEXT NOT NULL DEFAULT '[]',
    approval_strategy TEXT,
    memory_policy TEXT,
    stopping_conditions_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'registry_default',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_harness_profiles_status
ON agent_registry_harness_profiles(status, id);
