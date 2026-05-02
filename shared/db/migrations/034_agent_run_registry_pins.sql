ALTER TABLE agent_runs ADD COLUMN registry_version TEXT;
ALTER TABLE agent_runs ADD COLUMN registry_fingerprint TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_runs_registry_fingerprint
ON agent_runs(registry_fingerprint, created_at);
