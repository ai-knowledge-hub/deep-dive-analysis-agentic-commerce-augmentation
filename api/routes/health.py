from __future__ import annotations

from fastapi import APIRouter

from shared.config.env import get_settings
from shared.llm.clients import get_llm_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/llm")
def llm_health():
    settings = get_settings()
    providers = [
        ("openai", settings.openai_api_key),
        ("anthropic", settings.anthropic_api_key),
        ("gemini", settings.gemini_api_key),
        ("openrouter", settings.openrouter_api_key),
    ]
    results = {}
    for provider, key in providers:
        if not key:
            results[provider] = {"configured": False}
            continue
        try:
            get_llm_client(provider)
            results[provider] = {"configured": True}
        except Exception as exc:  # pragma: no cover
            results[provider] = {"configured": False, "error": str(exc)}
    return {"providers": results}


__all__ = ["router"]
