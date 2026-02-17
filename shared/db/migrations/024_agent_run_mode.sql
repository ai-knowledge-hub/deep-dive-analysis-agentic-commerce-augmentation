ALTER TABLE agent_runs
ADD COLUMN run_mode TEXT DEFAULT 'plan_only';

CREATE INDEX IF NOT EXISTS idx_agent_runs_mode_status
ON agent_runs(run_mode, status, created_at);

