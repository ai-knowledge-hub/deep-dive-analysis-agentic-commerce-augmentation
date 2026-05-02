ALTER TABLE agent_actions ADD COLUMN side_effects_json TEXT DEFAULT '[]';
ALTER TABLE agent_actions ADD COLUMN rollback_guidance TEXT;
