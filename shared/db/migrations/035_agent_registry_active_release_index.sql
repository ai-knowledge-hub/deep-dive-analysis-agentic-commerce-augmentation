CREATE INDEX IF NOT EXISTS idx_agent_registry_versions_status_created
ON agent_registry_versions(status, created_at DESC);
