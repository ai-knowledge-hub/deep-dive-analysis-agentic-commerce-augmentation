ALTER TABLE agent_registry_harness_profiles
ADD COLUMN allowed_effect_classes_json TEXT NOT NULL DEFAULT '[]';
