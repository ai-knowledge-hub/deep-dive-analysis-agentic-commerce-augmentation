ALTER TABLE experiment_runs
ADD COLUMN execution_mode TEXT DEFAULT 'simulation';

ALTER TABLE experiment_runs
ADD COLUMN retrieval_summary_json TEXT;
