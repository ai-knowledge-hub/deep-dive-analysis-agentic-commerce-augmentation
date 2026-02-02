CREATE TABLE IF NOT EXISTS skills_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT,
    content TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    metadata_json TEXT,
    changed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_skills_history_skill ON skills_history(skill_id);
