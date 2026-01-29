CREATE TABLE IF NOT EXISTS query_batteries (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT NOT NULL,
    name TEXT NOT NULL,
    purpose TEXT,
    generation_mode TEXT,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS query_battery_queries (
    id TEXT PRIMARY KEY,
    battery_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_type TEXT,
    intent_archetype TEXT,
    constraints_json TEXT,
    weight REAL DEFAULT 1.0,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (battery_id) REFERENCES query_batteries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT NOT NULL,
    battery_id TEXT,
    name TEXT NOT NULL,
    hypothesis_json TEXT,
    competitor_policy_json TEXT,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (battery_id) REFERENCES query_batteries(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS experiment_variants (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    label TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    simulation_run_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE CASCADE,
    FOREIGN KEY (query_id) REFERENCES query_battery_queries(id) ON DELETE CASCADE,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS experiment_metrics (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    variant_id TEXT,
    metrics_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_query_batteries_client ON query_batteries(client_id);
CREATE INDEX IF NOT EXISTS idx_query_batteries_product ON query_batteries(product_id);
CREATE INDEX IF NOT EXISTS idx_query_battery_queries_battery ON query_battery_queries(battery_id);
CREATE INDEX IF NOT EXISTS idx_experiments_client ON experiments(client_id);
CREATE INDEX IF NOT EXISTS idx_experiments_product ON experiments(product_id);
CREATE INDEX IF NOT EXISTS idx_experiments_battery ON experiments(battery_id);
CREATE INDEX IF NOT EXISTS idx_experiment_variants_experiment ON experiment_variants(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_experiment ON experiment_runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_variant ON experiment_runs(variant_id);
CREATE INDEX IF NOT EXISTS idx_experiment_metrics_experiment ON experiment_metrics(experiment_id);
