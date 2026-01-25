PRAGMA foreign_keys=OFF;
BEGIN;

CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS client_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'analyst',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (client_id, user_id)
);

INSERT OR IGNORE INTO clients (id, name) VALUES ('default', 'Default');

ALTER TABLE sessions ADD COLUMN client_id TEXT;
ALTER TABLE sessions ADD COLUMN brand_id TEXT;

ALTER TABLE goals ADD COLUMN client_id TEXT;
ALTER TABLE goals ADD COLUMN brand_id TEXT;

ALTER TABLE episodes ADD COLUMN client_id TEXT;

ALTER TABLE recommendations ADD COLUMN client_id TEXT;

ALTER TABLE semantic_memory ADD COLUMN client_id TEXT;

ALTER TABLE simulation_runs ADD COLUMN client_id TEXT;
ALTER TABLE simulation_runs ADD COLUMN brand_id TEXT;
ALTER TABLE simulation_runs ADD COLUMN product_id TEXT;

ALTER TABLE simulation_lessons ADD COLUMN client_id TEXT;

UPDATE sessions SET client_id = 'default' WHERE client_id IS NULL;
UPDATE goals SET client_id = 'default' WHERE client_id IS NULL;
UPDATE episodes SET client_id = 'default' WHERE client_id IS NULL;
UPDATE recommendations SET client_id = 'default' WHERE client_id IS NULL;
UPDATE semantic_memory SET client_id = 'default' WHERE client_id IS NULL;
UPDATE simulation_runs SET client_id = 'default' WHERE client_id IS NULL;
UPDATE simulation_lessons SET client_id = 'default' WHERE client_id IS NULL;

CREATE TABLE IF NOT EXISTS semantic_memory_new (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    client_id TEXT,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    embedding BLOB,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE (client_id, user_id, key)
);

INSERT INTO semantic_memory_new (
    id,
    user_id,
    client_id,
    key,
    value_json,
    embedding,
    created_at,
    updated_at
)
SELECT
    id,
    user_id,
    client_id,
    key,
    value_json,
    embedding,
    created_at,
    updated_at
FROM semantic_memory;

DROP TABLE semantic_memory;
ALTER TABLE semantic_memory_new RENAME TO semantic_memory;

CREATE INDEX IF NOT EXISTS idx_sessions_client ON sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_goals_client ON goals(client_id);
CREATE INDEX IF NOT EXISTS idx_semantic_client_key ON semantic_memory(client_id, user_id, key);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_client ON simulation_runs(client_id);
CREATE INDEX IF NOT EXISTS idx_simulation_lessons_client ON simulation_lessons(client_id);

COMMIT;
PRAGMA foreign_keys=ON;
