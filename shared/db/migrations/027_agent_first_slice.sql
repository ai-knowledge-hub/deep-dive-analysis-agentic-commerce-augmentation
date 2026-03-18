CREATE TABLE IF NOT EXISTS principals (
    id TEXT PRIMARY KEY,
    principal_type TEXT NOT NULL CHECK (principal_type IN ('human', 'internal_agent', 'external_agent')),
    tenant_id TEXT,
    display_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES clients(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_principals_tenant_type
ON principals(tenant_id, principal_type, status);

CREATE TABLE IF NOT EXISTS policy_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    effect_classes_json TEXT NOT NULL,
    approval_rules_json TEXT NOT NULL,
    budget_defaults_json TEXT NOT NULL,
    fallback_rules_json TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    tenant_id TEXT,
    name TEXT NOT NULL,
    default_harness_id TEXT,
    default_policy_profile_id TEXT,
    risk_tier TEXT,
    channel_type TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (principal_id) REFERENCES principals(id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES clients(id) ON DELETE SET NULL,
    FOREIGN KEY (default_policy_profile_id) REFERENCES policy_profiles(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_principal
ON agent_profiles(principal_id, tenant_id);

ALTER TABLE agent_runs ADD COLUMN principal_type TEXT;
ALTER TABLE agent_runs ADD COLUMN principal_id TEXT;
ALTER TABLE agent_runs ADD COLUMN agent_profile_id TEXT;
ALTER TABLE agent_runs ADD COLUMN harness_id TEXT;
ALTER TABLE agent_runs ADD COLUMN policy_profile_id TEXT;
ALTER TABLE agent_runs ADD COLUMN idempotency_key TEXT;
ALTER TABLE agent_runs ADD COLUMN trace_id TEXT;
ALTER TABLE agent_runs ADD COLUMN root_run_id TEXT;
ALTER TABLE agent_runs ADD COLUMN parent_run_id TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_runs_principal
ON agent_runs(principal_type, principal_id, created_at);

CREATE INDEX IF NOT EXISTS idx_agent_runs_policy_profile
ON agent_runs(policy_profile_id, status, created_at);

ALTER TABLE agent_actions ADD COLUMN tool_id TEXT;
ALTER TABLE agent_actions ADD COLUMN skill_id TEXT;
ALTER TABLE agent_actions ADD COLUMN effect_class TEXT;
ALTER TABLE agent_actions ADD COLUMN receipt_id TEXT;
ALTER TABLE agent_actions ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE agent_actions ADD COLUMN dedupe_key TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_actions_tool_status
ON agent_actions(tool_id, status, created_at);

ALTER TABLE agent_events ADD COLUMN principal_type TEXT;
ALTER TABLE agent_events ADD COLUMN principal_id TEXT;
ALTER TABLE agent_events ADD COLUMN tool_id TEXT;
ALTER TABLE agent_events ADD COLUMN skill_id TEXT;
ALTER TABLE agent_events ADD COLUMN effect_class TEXT;
ALTER TABLE agent_events ADD COLUMN trace_id TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_events_trace
ON agent_events(trace_id, created_at);

INSERT OR IGNORE INTO policy_profiles (
    id,
    name,
    effect_classes_json,
    approval_rules_json,
    budget_defaults_json,
    fallback_rules_json,
    metadata_json
)
VALUES
(
    'human_approval_required',
    'Human Approval Required',
    json('["read","recommend","write_low_risk","write_high_risk","external_side_effect"]'),
    json('{"default":"human_approval_required"}'),
    json('{}'),
    json('{}'),
    json('{"seeded_by":"027_agent_first_slice.sql"}')
),
(
    'safe_auto',
    'Safe Auto',
    json('["read","recommend","write_low_risk"]'),
    json('{"default":"auto_for_allowed_effects","escalate":["write_high_risk","external_side_effect"]}'),
    json('{}'),
    json('{"browser_fallback":"approval_required","cli_fallback":"approval_required"}'),
    json('{"seeded_by":"027_agent_first_slice.sql"}')
),
(
    'observe',
    'Observe',
    json('["read","recommend"]'),
    json('{"default":"no_side_effects"}'),
    json('{}'),
    json('{}'),
    json('{"seeded_by":"027_agent_first_slice.sql"}')
);

UPDATE agent_runs
SET principal_type = COALESCE(principal_type, 'human');

UPDATE agent_runs
SET policy_profile_id = COALESCE(
    policy_profile_id,
    CASE
        WHEN run_mode = 'auto_execute_safe' THEN 'safe_auto'
        ELSE 'human_approval_required'
    END
);
