CREATE TABLE IF NOT EXISTS world_states (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    vertical TEXT,
    state_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS belief_revisions (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    hypothesis_key TEXT NOT NULL,
    prior REAL NOT NULL,
    likelihood REAL NOT NULL,
    posterior REAL NOT NULL,
    confidence REAL NOT NULL,
    evidence_ref_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS decision_events (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    policy_action TEXT NOT NULL,
    uncertainty REAL,
    expected_gain REAL,
    selected_reason TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_world_states_scope
ON world_states(client_id, brand_id, product_id, created_at);

CREATE INDEX IF NOT EXISTS idx_belief_revisions_scope
ON belief_revisions(client_id, brand_id, product_id, hypothesis_key, created_at);

CREATE INDEX IF NOT EXISTS idx_decision_events_scope
ON decision_events(client_id, brand_id, product_id, created_at);

