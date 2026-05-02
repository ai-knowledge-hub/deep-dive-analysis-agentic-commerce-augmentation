CREATE TABLE IF NOT EXISTS agent_registry_audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    previous_registry_fingerprint TEXT,
    registry_fingerprint TEXT NOT NULL,
    registry_version TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'static_code',
    diff_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (previous_registry_fingerprint)
        REFERENCES agent_registry_versions(registry_fingerprint)
        ON DELETE SET NULL,
    FOREIGN KEY (registry_fingerprint)
        REFERENCES agent_registry_versions(registry_fingerprint)
        ON DELETE CASCADE,
    UNIQUE (event_type, previous_registry_fingerprint, registry_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_audit_events_fingerprint
ON agent_registry_audit_events(registry_fingerprint, created_at DESC);
