PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS replay_records (
    id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    user_id TEXT,
    client_id TEXT,
    session_id TEXT,
    record_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_replay_records_client ON replay_records(client_id);
CREATE INDEX IF NOT EXISTS idx_replay_records_user ON replay_records(user_id);
CREATE INDEX IF NOT EXISTS idx_replay_records_session ON replay_records(session_id);
CREATE INDEX IF NOT EXISTS idx_replay_records_entity ON replay_records(entity_type, entity_id);

