from __future__ import annotations

import json
from pathlib import Path
import os
from typing import Any, Dict, Optional

from application.ports.deps import (
    ClientsStore,
    PlatformProfilesStore,
    SkillsStore,
    LLMProviderConfigsStore,
)
from application.services.admin.canonical_intent_spec_service import (
    CanonicalIntentSpecService,
    DEFAULT_SOURCE_PRIORITY,
)
from application.services.admin.skill_defaults import (
    ensure_default_skill,
    default_skill_names,
)


class AdminService:
    def __init__(
        self,
        *,
        clients_repo: ClientsStore,
        platform_profiles_repo: PlatformProfilesStore,
        skills_repo: SkillsStore,
        llm_provider_configs_repo: LLMProviderConfigsStore,
    ) -> None:
        self._clients = clients_repo
        self._platform_profiles = platform_profiles_repo
        self._skills = skills_repo
        self._canonical_spec = CanonicalIntentSpecService(clients_repo=clients_repo)
        self._llm_configs = llm_provider_configs_repo

    def create_client(
        self, *, client_id: str, name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._clients.create_client(
            client_id=client_id, name=name, metadata=metadata or {}
        )

    def list_clients(self) -> list[Dict[str, Any]]:
        return self._clients.list_clients()

    def create_brand(
        self,
        *,
        brand_id: str,
        client_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._clients.create_brand(
            brand_id=brand_id, client_id=client_id, name=name, metadata=metadata or {}
        )

    def list_brands(self, *, client_id: str) -> list[Dict[str, Any]]:
        return self._clients.list_brands(client_id=client_id)

    def create_product(
        self,
        *,
        product_id: str,
        brand_id: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._clients.create_product(
            product_id=product_id,
            brand_id=brand_id,
            name=name,
            description=description,
            metadata=metadata or {},
        )

    def list_products(self, *, brand_id: str) -> list[Dict[str, Any]]:
        return self._clients.list_products(brand_id=brand_id)

    def update_product(
        self,
        *,
        product_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | None:
        existing = self._clients.get_product(product_id=product_id)
        if not existing:
            return None
        current_metadata = dict(existing.get("metadata") or {})
        next_metadata = (
            _deep_merge_dict(current_metadata, metadata or {})
            if metadata is not None
            else current_metadata
        )
        next_description = (
            description if description is not None else existing.get("description")
        )
        if name is not None and name.strip():
            next_metadata["display_name"] = name.strip()
        return self._clients.update_product(
            product_id=product_id,
            description=next_description,
            metadata=next_metadata,
        )

    def autofill_product_canonical_spec(
        self,
        *,
        product_id: str,
        source_priority: Optional[list[str]] = None,
        apply: bool = False,
    ) -> Dict[str, Any]:
        return self._canonical_spec.autofill(
            product_id=product_id,
            source_priority=source_priority or DEFAULT_SOURCE_PRIORITY,
            apply=apply,
        )

    def add_client_user(
        self, *, client_id: str, member_user_id: str, role: Optional[str] = None
    ) -> Dict[str, Any]:
        return self._clients.add_client_user(
            client_id=client_id, user_id=member_user_id, role=role
        )

    def list_client_users(self, *, client_id: str) -> list[Dict[str, Any]]:
        return self._clients.list_client_users(client_id=client_id)

    def get_platform_profile(self) -> Dict[str, Any]:
        existing = self._platform_profiles.get_platform_profile()
        if existing:
            return existing
        fallback = _load_default_platform_profile()
        if not fallback:
            return {}
        return self._platform_profiles.ensure_platform_profile(
            name=fallback.get("name") or "UCP Platform Profile",
            version=fallback.get("version") or "2026-01-11",
            profile=fallback,
        )

    def ensure_platform_profile(
        self, *, name: str, version: str, profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._platform_profiles.ensure_platform_profile(
            name=name, version=version, profile=profile
        )

    def update_platform_profile(
        self, *, name: str, version: str, profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._platform_profiles.upsert_platform_profile(
            name=name, version=version, profile=profile
        )

    def list_skill_names(self) -> list[str]:
        return default_skill_names()

    def get_skill(self, *, name: str) -> Dict[str, Any] | None:
        return ensure_default_skill(skills_repo=self._skills, name=name)

    def update_skill(
        self,
        *,
        name: str,
        description: str,
        version: str,
        content: str,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        existing = self._skills.get_skill(name=name, include_disabled=True)
        skill_id = existing.get("id") if existing else name
        return self._skills.upsert_skill(
            skill_id=skill_id,
            name=name,
            description=description,
            version=version,
            content=content,
            enabled=enabled,
            metadata=metadata or {},
        )

    def list_skill_history(self, *, name: str, limit: int = 10) -> list[Dict[str, Any]]:
        if hasattr(self._skills, "list_skill_history"):
            return self._skills.list_skill_history(name=name, limit=limit)  # type: ignore[no-any-return]
        return []

    # ------------------------------------------------------------------ LLM config

    def list_llm_provider_configs(self) -> list[Dict[str, Any]]:
        return self._llm_configs.list_configs()

    def get_llm_provider_summary(self) -> Dict[str, Any]:
        from shared.config.env import get_settings

        settings = get_settings()
        configs = {item["provider"]: item for item in self._llm_configs.list_configs()}
        providers = {}
        defaults = _default_provider_models()
        for provider in ("openai", "anthropic", "gemini", "openrouter"):
            config = configs.get(provider, {})
            key = config.get("api_key")
            validation_key = config.get("validation_api_key")
            model = config.get("model")
            validation_model = config.get("validation_model")
            if provider == "openai":
                key = key or settings.openai_api_key
                validation_key = validation_key or settings.openai_validation_api_key
                model = model or settings.openai_model
                validation_model = (
                    validation_model
                    or settings.openai_validation_model
                    or settings.openai_model
                )
            elif provider == "anthropic":
                key = key or settings.anthropic_api_key
                validation_key = validation_key or settings.anthropic_validation_api_key
                model = model or settings.anthropic_model
                validation_model = (
                    validation_model
                    or settings.anthropic_validation_model
                    or settings.anthropic_model
                )
            elif provider == "gemini":
                key = key or settings.gemini_api_key
                validation_key = validation_key or settings.gemini_validation_api_key
                model = model or settings.gemini_model
                validation_model = (
                    validation_model
                    or settings.gemini_validation_model
                    or settings.gemini_model
                )
            elif provider == "openrouter":
                key = key or settings.openrouter_api_key
                validation_key = (
                    validation_key or settings.openrouter_validation_api_key
                )
                model = model or settings.openrouter_model
                validation_model = (
                    validation_model
                    or settings.openrouter_validation_model
                    or settings.openrouter_model
                )
            providers[provider] = {
                "configured": bool(key or validation_key),
                "chat_configured": bool(key),
                "validation_configured": bool(validation_key),
                "model": model or defaults.get(provider),
                "validation_model": validation_model or defaults.get(provider),
                "is_active": bool(config.get("is_active")),
            }
        active_provider = (
            self._llm_configs.get_active_provider() or settings.llm_provider
        )
        for provider in providers:
            providers[provider]["is_active"] = providers[provider].get("is_active") or (
                provider == active_provider
            )
        return {"active_provider": active_provider, "providers": providers}

    def update_llm_provider_config(
        self,
        *,
        provider: str,
        api_key: Optional[str] = None,
        validation_api_key: Optional[str] = None,
        model: Optional[str] = None,
        validation_model: Optional[str] = None,
        activate: Optional[bool] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        from shared.config.env import get_settings

        settings = get_settings()
        existing = self._llm_configs.get_config(provider=provider) or {}
        next_api_key = _coalesce_update(
            api_key,
            existing.get("api_key") or _provider_key_from_settings(provider, settings),
        )
        next_validation_key = _coalesce_update(
            validation_api_key,
            existing.get("validation_api_key")
            or _provider_validation_key_from_settings(provider, settings),
        )
        next_model = _coalesce_update(
            model,
            existing.get("model") or _provider_model_from_settings(provider, settings),
        )
        next_validation_model = _coalesce_update(
            validation_model,
            existing.get("validation_model")
            or _provider_validation_model_from_settings(provider, settings),
        )
        if activate is True:
            self._llm_configs.set_active_provider(provider=provider)
        config = self._llm_configs.upsert_config(
            provider=provider,
            api_key=next_api_key,
            validation_api_key=next_validation_key,
            model=next_model,
            validation_model=next_validation_model,
            is_active=True if activate else None,
            updated_by=updated_by,
        )
        self._apply_llm_env(
            provider=provider,
            config=config,
            activate=activate or config.get("is_active"),
        )
        return config

    def set_active_llm_provider(
        self,
        *,
        provider: str,
        model: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        from shared.config.env import get_settings

        settings = get_settings()
        existing = self._llm_configs.get_config(provider=provider) or {}
        next_model = (
            model or existing.get("model") or _default_provider_models().get(provider)
        )
        api_key = existing.get("api_key") or _provider_key_from_settings(
            provider, settings
        )
        validation_api_key = existing.get(
            "validation_api_key"
        ) or _provider_validation_key_from_settings(provider, settings)
        validation_model = existing.get(
            "validation_model"
        ) or _provider_validation_model_from_settings(provider, settings)
        self._llm_configs.set_active_provider(provider=provider)
        config = self._llm_configs.upsert_config(
            provider=provider,
            api_key=api_key,
            validation_api_key=validation_api_key,
            model=next_model,
            validation_model=validation_model,
            is_active=True,
            updated_by=updated_by,
        )
        self._apply_llm_env(provider=provider, config=config, activate=True)
        return config

    def _apply_llm_env(
        self, *, provider: str, config: Dict[str, Any], activate: Optional[bool]
    ) -> None:
        updates = _provider_env_updates(provider, config)
        if activate:
            updates["LLM_PROVIDER"] = provider
        _update_env_file(Path(".env.local"), updates)
        _apply_env_updates(updates)
        _refresh_llm_clients()


def _load_default_platform_profile() -> Dict[str, Any] | None:
    path = Path("data/platform_profiles/ucp_platform_2026-01-11.json")
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _deep_merge_dict(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _default_provider_models() -> Dict[str, str]:
    return {
        "openrouter": "openai/gpt-oss-120b",
        "openai": "gpt-5.2-2025-12-11",
        "anthropic": "claude-sonnet-4-5-20250929",
        "gemini": "gemini-3-flash-preview",
    }


def _coalesce_update(value: Optional[str], existing: Optional[str]) -> Optional[str]:
    if value is None:
        return existing
    if value == "":
        return None
    return value


def _provider_env_updates(
    provider: str, config: Dict[str, Any]
) -> Dict[str, Optional[str]]:
    updates: Dict[str, Optional[str]] = {}
    model = config.get("model")
    validation_model = config.get("validation_model")
    api_key = config.get("api_key")
    validation_key = config.get("validation_api_key")
    if provider == "openai":
        updates["OPENAI_API_KEY"] = api_key
        updates["OPENAI_MODEL"] = model
        updates["OPENAI_VALIDATION_API_KEY"] = validation_key
        updates["OPENAI_VALIDATION_MODEL"] = validation_model
    elif provider in {"anthropic", "claude"}:
        updates["ANTHROPIC_API_KEY"] = api_key
        updates["ANTHROPIC_MODEL"] = model
        updates["ANTHROPIC_VALIDATION_API_KEY"] = validation_key
        updates["ANTHROPIC_VALIDATION_MODEL"] = validation_model
    elif provider == "gemini":
        updates["GEMINI_API_KEY"] = api_key
        updates["GEMINI_MODEL"] = model
        updates["GEMINI_VALIDATION_API_KEY"] = validation_key
        updates["GEMINI_VALIDATION_MODEL"] = validation_model
    elif provider == "openrouter":
        updates["OPENROUTER_API_KEY"] = api_key
        updates["OPENROUTER_MODEL"] = model
        updates["OPENROUTER_VALIDATION_API_KEY"] = validation_key
        updates["OPENROUTER_VALIDATION_MODEL"] = validation_model
    return updates


def _provider_key_from_settings(provider: str, settings) -> Optional[str]:
    if provider == "openai":
        return settings.openai_api_key
    if provider in {"anthropic", "claude"}:
        return settings.anthropic_api_key
    if provider == "gemini":
        return settings.gemini_api_key
    if provider == "openrouter":
        return settings.openrouter_api_key
    return None


def _provider_validation_key_from_settings(provider: str, settings) -> Optional[str]:
    if provider == "openai":
        return settings.openai_validation_api_key
    if provider in {"anthropic", "claude"}:
        return settings.anthropic_validation_api_key
    if provider == "gemini":
        return settings.gemini_validation_api_key
    if provider == "openrouter":
        return settings.openrouter_validation_api_key
    return None


def _provider_validation_model_from_settings(provider: str, settings) -> Optional[str]:
    if provider == "openai":
        return settings.openai_validation_model
    if provider in {"anthropic", "claude"}:
        return settings.anthropic_validation_model
    if provider == "gemini":
        return settings.gemini_validation_model
    if provider == "openrouter":
        return settings.openrouter_validation_model
    return None


def _provider_model_from_settings(provider: str, settings) -> Optional[str]:
    if provider == "openai":
        return settings.openai_model
    if provider in {"anthropic", "claude"}:
        return settings.anthropic_model
    if provider == "gemini":
        return settings.gemini_model
    if provider == "openrouter":
        return settings.openrouter_model
    return None


def _update_env_file(path: Path, updates: Dict[str, Optional[str]]) -> None:
    if not updates:
        return
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()
    seen = set()
    next_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            seen.add(key)
            value = updates[key]
            if value is None:
                continue
            next_lines.append(f"{key}={value}")
        else:
            next_lines.append(line)
    for key, value in updates.items():
        if key in seen:
            continue
        if value is None:
            continue
        next_lines.append(f"{key}={value}")
    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def _apply_env_updates(updates: Dict[str, Optional[str]]) -> None:
    for key, value in updates.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _refresh_llm_clients() -> None:
    from shared.config.env import get_settings
    from shared.llm.clients import reset_clients

    get_settings.cache_clear()
    reset_clients()
