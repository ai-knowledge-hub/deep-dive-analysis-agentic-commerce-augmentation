from __future__ import annotations

from typing import Dict

from shared.config.env import settings


def default_versions(*, scoring_version: str = "alignment-v1") -> Dict[str, str]:
    model = (
        settings.openrouter_model
        if settings.llm_provider == "openrouter"
        else settings.gemini_model
    )
    return {
        "app_env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "llm_model": model,
        "scoring": scoring_version,
    }


__all__ = ["default_versions"]
