-- SQLite schema for discovery-first memory + session storage.
-- This schema supports intent inference, alignment, and product analytics.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at TEXT DEFAULT (datetime('now')),
    preferences_json TEXT,
    metadata_json TEXT
);

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
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS platform_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    profile_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS client_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'analyst',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (client_id, user_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    client_id TEXT,
    brand_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    state_json TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    client_id TEXT,
    brand_id TEXT,
    goal_text TEXT NOT NULL,
    goal_embedding BLOB,
    domain TEXT,
    importance REAL DEFAULT 0.5,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    speaker TEXT CHECK (speaker IN ('user', 'agent')),
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    client_id TEXT,
    outcome TEXT,
    takeaways_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    client_id TEXT,
    product_ids_json TEXT NOT NULL,
    alignment_score REAL,
    context_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS semantic_memory (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    client_id TEXT,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    embedding BLOB,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
    UNIQUE (client_id, user_id, key)
);

CREATE TABLE IF NOT EXISTS intent_embeddings (
    id TEXT PRIMARY KEY,
    intent_text TEXT NOT NULL,
    embedding BLOB,
    payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS product_embeddings (
    product_id TEXT PRIMARY KEY,
    embedding BLOB,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    session_id TEXT,
    client_id TEXT,
    brand_id TEXT,
    product_id TEXT,
    query TEXT NOT NULL,
    scenario_json TEXT,
    products_json TEXT,
    result_json TEXT,
    retest_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS simulation_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    user_id TEXT,
    client_id TEXT,
    lesson TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS query_batteries (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT NOT NULL,
    name TEXT NOT NULL,
    purpose TEXT,
    generation_mode TEXT,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS query_battery_queries (
    id TEXT PRIMARY KEY,
    battery_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_type TEXT,
    intent_archetype TEXT,
    constraints_json TEXT,
    weight REAL DEFAULT 1.0,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (battery_id) REFERENCES query_batteries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    product_id TEXT NOT NULL,
    battery_id TEXT,
    name TEXT NOT NULL,
    hypothesis_json TEXT,
    competitor_policy_json TEXT,
    status TEXT DEFAULT 'draft',
    schedule_enabled INTEGER DEFAULT 0,
    schedule_interval_minutes INTEGER,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (battery_id) REFERENCES query_batteries(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS experiment_variants (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    label TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    simulation_run_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE CASCADE,
    FOREIGN KEY (query_id) REFERENCES query_battery_queries(id) ON DELETE CASCADE,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS experiment_metrics (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    variant_id TEXT,
    metrics_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE SET NULL
);

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

CREATE TABLE IF NOT EXISTS experiment_recommendations (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    recommendation_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

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

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_client ON sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_goals_user ON goals(user_id);
CREATE INDEX IF NOT EXISTS idx_goals_client ON goals(client_id);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_semantic_client_key ON semantic_memory(client_id, user_id, key);
CREATE INDEX IF NOT EXISTS idx_intent_embeddings_text ON intent_embeddings(intent_text);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_user ON simulation_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_client ON simulation_runs(client_id);
CREATE INDEX IF NOT EXISTS idx_simulation_lessons_user ON simulation_lessons(user_id);
CREATE INDEX IF NOT EXISTS idx_simulation_lessons_client ON simulation_lessons(client_id);
CREATE INDEX IF NOT EXISTS idx_query_batteries_client ON query_batteries(client_id);
CREATE INDEX IF NOT EXISTS idx_query_batteries_product ON query_batteries(product_id);
CREATE INDEX IF NOT EXISTS idx_query_battery_queries_battery ON query_battery_queries(battery_id);
CREATE INDEX IF NOT EXISTS idx_experiments_client ON experiments(client_id);
CREATE INDEX IF NOT EXISTS idx_experiments_product ON experiments(product_id);
CREATE INDEX IF NOT EXISTS idx_experiments_battery ON experiments(battery_id);
CREATE INDEX IF NOT EXISTS idx_experiments_next_run ON experiments(next_run_at);
CREATE INDEX IF NOT EXISTS idx_llm_provider_configs_active ON llm_provider_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_copy_revisions_client ON copy_revisions(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_copy_revisions_product ON copy_revisions(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_copy_revisions_source ON copy_revisions(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_experiment_metrics_experiment ON experiment_metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_validations_experiment ON experiment_validations(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_validations_brand ON experiment_validations(brand_id);
CREATE INDEX IF NOT EXISTS idx_experiment_validations_client ON experiment_validations(client_id);
CREATE INDEX IF NOT EXISTS idx_experiment_calibrations_brand ON experiment_calibrations(brand_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_client ON analytics_events(client_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_product ON analytics_events(product_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_experiment ON analytics_events(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_variants_experiment ON experiment_variants(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_experiment ON experiment_runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_variant ON experiment_runs(variant_id);
CREATE INDEX IF NOT EXISTS idx_brand_beliefs_client ON brand_beliefs(client_id);
CREATE INDEX IF NOT EXISTS idx_brand_beliefs_brand ON brand_beliefs(brand_id);
CREATE INDEX IF NOT EXISTS idx_brand_beliefs_product ON brand_beliefs(product_id);
CREATE INDEX IF NOT EXISTS idx_brand_beliefs_created ON brand_beliefs(created_at);
CREATE INDEX IF NOT EXISTS idx_audience_archetypes_client ON audience_archetypes(client_id);
CREATE INDEX IF NOT EXISTS idx_audience_archetypes_brand ON audience_archetypes(brand_id);
CREATE INDEX IF NOT EXISTS idx_audience_archetypes_domain ON audience_archetypes(domain_vertical);
CREATE INDEX IF NOT EXISTS idx_experiment_recommendations_experiment
ON experiment_recommendations(experiment_id);

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
