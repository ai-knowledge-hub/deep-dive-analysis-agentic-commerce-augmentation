ALTER TABLE experiments ADD COLUMN schedule_enabled INTEGER DEFAULT 0;
ALTER TABLE experiments ADD COLUMN schedule_interval_minutes INTEGER;
ALTER TABLE experiments ADD COLUMN last_run_at TEXT;
ALTER TABLE experiments ADD COLUMN next_run_at TEXT;

CREATE INDEX IF NOT EXISTS idx_experiments_next_run ON experiments(next_run_at);
