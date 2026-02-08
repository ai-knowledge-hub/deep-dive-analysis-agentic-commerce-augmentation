CREATE TABLE IF NOT EXISTS memory_artifacts (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT,
    vertical TEXT,
    artifact_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    quality_score REAL DEFAULT 0,
    support_count INTEGER DEFAULT 0,
    source TEXT,
    last_used_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_artifacts_scope
ON memory_artifacts(client_id, brand_id, vertical, artifact_type);

CREATE INDEX IF NOT EXISTS idx_memory_artifacts_quality
ON memory_artifacts(quality_score, support_count, created_at);

