CREATE TABLE IF NOT EXISTS brand_beliefs (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT NOT NULL,
    product_id TEXT,
    hypothesis_json TEXT,
    evidence_json TEXT,
    recommendation TEXT,
    confidence REAL,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_brand_beliefs_client ON brand_beliefs(client_id);
CREATE INDEX IF NOT EXISTS idx_brand_beliefs_brand ON brand_beliefs(brand_id);
CREATE INDEX IF NOT EXISTS idx_brand_beliefs_product ON brand_beliefs(product_id);
CREATE INDEX IF NOT EXISTS idx_brand_beliefs_created ON brand_beliefs(created_at);
