ALTER TABLE validation_jobs
ADD COLUMN integration_type TEXT;

ALTER TABLE validation_jobs
ADD COLUMN provider_run_id TEXT;

ALTER TABLE validation_jobs
ADD COLUMN callback_verified INTEGER DEFAULT 0;

ALTER TABLE validation_results
ADD COLUMN source TEXT DEFAULT 'synthetic';

ALTER TABLE validation_results
ADD COLUMN callback_verified INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_validation_jobs_provider_run
ON validation_jobs(provider_run_id);
