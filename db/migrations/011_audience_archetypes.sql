PRAGMA foreign_keys=OFF;
BEGIN;

CREATE TABLE IF NOT EXISTS audience_archetypes (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    domain_vertical TEXT,
    label TEXT NOT NULL,
    description TEXT,
    archetype_json TEXT,
    source TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audience_archetypes_client
    ON audience_archetypes(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audience_archetypes_brand
    ON audience_archetypes(brand_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audience_archetypes_domain
    ON audience_archetypes(domain_vertical, created_at);

COMMIT;
PRAGMA foreign_keys=ON;
