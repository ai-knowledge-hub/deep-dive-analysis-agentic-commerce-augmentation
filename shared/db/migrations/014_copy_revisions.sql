CREATE TABLE IF NOT EXISTS copy_revisions (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    source_variant_id TEXT,
    base_description TEXT NOT NULL,
    candidate_description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    notes TEXT,
    metadata_json TEXT,
    created_by TEXT,
    approved_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (source_variant_id) REFERENCES experiment_variants(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_copy_revisions_client ON copy_revisions(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_copy_revisions_product ON copy_revisions(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_copy_revisions_source ON copy_revisions(source_type, source_id);
