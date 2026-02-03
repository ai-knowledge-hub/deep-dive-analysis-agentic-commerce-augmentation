PRAGMA foreign_keys=OFF;
BEGIN;

CREATE TABLE IF NOT EXISTS experiment_validations (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    variant_id TEXT,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    platform TEXT,
    query_text TEXT,
    observed_products_json TEXT,
    observed_winner_variant_id TEXT,
    observed_position INTEGER,
    notes TEXT,
    is_correct INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_experiment_validations_experiment
    ON experiment_validations(experiment_id, created_at);
CREATE INDEX IF NOT EXISTS idx_experiment_validations_brand
    ON experiment_validations(brand_id, created_at);
CREATE INDEX IF NOT EXISTS idx_experiment_validations_client
    ON experiment_validations(client_id, created_at);

CREATE TABLE IF NOT EXISTS experiment_calibrations (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    verified_runs INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0.0,
    last_updated TEXT DEFAULT (datetime('now')),
    metadata_json TEXT,
    UNIQUE (brand_id),
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_experiment_calibrations_brand
    ON experiment_calibrations(brand_id);

CREATE TABLE IF NOT EXISTS analytics_events (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    variant_id TEXT,
    experiment_id TEXT,
    event_type TEXT NOT NULL,
    source TEXT,
    event_timestamp TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE SET NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_client
    ON analytics_events(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_product
    ON analytics_events(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_experiment
    ON analytics_events(experiment_id, created_at);

COMMIT;
PRAGMA foreign_keys=ON;
