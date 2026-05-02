CREATE TABLE IF NOT EXISTS agent_registry_versions (
    id TEXT PRIMARY KEY,
    registry_version TEXT NOT NULL,
    registry_fingerprint TEXT NOT NULL UNIQUE,
    hash_algorithm TEXT NOT NULL DEFAULT 'sha256',
    source TEXT NOT NULL DEFAULT 'static_code',
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_versions_version_created
ON agent_registry_versions(registry_version, created_at DESC);
