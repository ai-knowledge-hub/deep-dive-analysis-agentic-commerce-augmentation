ALTER TABLE agent_runs
ADD COLUMN lock_token TEXT;

ALTER TABLE agent_runs
ADD COLUMN lock_acquired_at TEXT;

ALTER TABLE agent_runs
ADD COLUMN lock_expires_at TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_runs_lock_expires
ON agent_runs(lock_expires_at);
