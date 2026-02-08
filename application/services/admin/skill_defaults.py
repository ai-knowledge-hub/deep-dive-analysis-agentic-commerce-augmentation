from __future__ import annotations

from typing import Any, Dict

from application.services.evidence.signal_extractor import (
    DEFAULT_SKILL_CONTENT as DEFAULT_SIGNAL_SKILL,
    SKILL_DESCRIPTION as SIGNAL_DESCRIPTION,
    SKILL_ID as SIGNAL_ID,
    SKILL_NAME as SIGNAL_NAME,
    SKILL_VERSION as SIGNAL_VERSION,
)


COPY_SKILL_ID = "copy-generator-v1"
COPY_SKILL_NAME = "copy_generator"
COPY_SKILL_VERSION = "2026-02-01"
COPY_SKILL_DESCRIPTION = (
    "Rewrite product copy to align with intent signals and brand tone."
)
COPY_SKILL_CONTENT = """# Copy Generation Skill

You rewrite product copy to align with user intent signals while preserving brand tone.
You should output JSON ONLY and follow the schema exactly.

## Inputs
- intent_signals: concepts to emphasize
- missing_signals: concepts to add
- brand_tone: short tone summary (optional)
- source_copy: existing product copy
- feed_copy: existing ACP/UCP feed description (optional)

## Output JSON schema
{
  "web_copy": "rewritten web description",
  "feed_copy": "rewritten feed description",
  "notes": ["short bullet notes about changes"]
}
"""


DEFAULT_SKILLS: Dict[str, Dict[str, Any]] = {
    SIGNAL_NAME: {
        "skill_id": SIGNAL_ID,
        "name": SIGNAL_NAME,
        "description": SIGNAL_DESCRIPTION,
        "version": SIGNAL_VERSION,
        "content": DEFAULT_SIGNAL_SKILL,
        "enabled": True,
        "metadata": {"purpose": "signal_extraction"},
    },
    COPY_SKILL_NAME: {
        "skill_id": COPY_SKILL_ID,
        "name": COPY_SKILL_NAME,
        "description": COPY_SKILL_DESCRIPTION,
        "version": COPY_SKILL_VERSION,
        "content": COPY_SKILL_CONTENT,
        "enabled": True,
        "metadata": {"purpose": "copy_generation"},
    },
}


def default_skill_names() -> list[str]:
    return list(DEFAULT_SKILLS.keys())


def ensure_default_skill(
    *,
    skills_repo,
    name: str,
) -> Dict[str, Any] | None:
    existing = skills_repo.get_skill(name=name, include_disabled=True)
    if existing:
        return existing
    definition = DEFAULT_SKILLS.get(name)
    if not definition:
        return None
    return skills_repo.upsert_skill(**definition)


__all__ = [
    "COPY_SKILL_NAME",
    "DEFAULT_SKILLS",
    "default_skill_names",
    "ensure_default_skill",
]
