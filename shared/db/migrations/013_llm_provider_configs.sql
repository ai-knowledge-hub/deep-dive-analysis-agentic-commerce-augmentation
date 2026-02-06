CREATE TABLE IF NOT EXISTS llm_provider_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    api_key TEXT,
    validation_api_key TEXT,
    model TEXT,
    validation_model TEXT,
    is_active INTEGER DEFAULT 0,
    updated_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE (provider)
);
