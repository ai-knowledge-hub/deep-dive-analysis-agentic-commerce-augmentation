from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from application.ports.deps import ClientsStore, PlatformProfilesStore, SkillsStore
from application.services.canonical_intent_spec_service import (
    CanonicalIntentSpecService,
    DEFAULT_SOURCE_PRIORITY,
)
from application.services.skill_defaults import (
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
    ) -> None:
        self._clients = clients_repo
        self._platform_profiles = platform_profiles_repo
        self._skills = skills_repo
        self._canonical_spec = CanonicalIntentSpecService(clients_repo=clients_repo)

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
