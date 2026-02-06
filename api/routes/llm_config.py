from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from api.composition import default_deps
from api.utils.tenancy import is_admin
from application.services.admin_service import AdminService

router = APIRouter(prefix="/llm", tags=["llm"])

deps = default_deps()
admin_service = AdminService(
    clients_repo=deps.clients,
    platform_profiles_repo=deps.platform_profiles,
    skills_repo=deps.skills,
    llm_provider_configs_repo=deps.llm_provider_configs,
)


@router.get("/config")
def get_llm_config(user_id: Optional[str] = None):
    summary = admin_service.get_llm_provider_summary()
    return {
        "can_manage": is_admin(user_id),
        "active_provider": summary.get("active_provider"),
        "providers": summary.get("providers"),
    }


__all__ = ["router"]
