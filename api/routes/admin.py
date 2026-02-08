from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, HTTPException
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from api.utils.tenancy import require_admin
from application.services.admin.service import AdminService
from application.services.loop.loop_maintenance_service import LoopMaintenanceService
from api.composition import default_deps

if APIRouter:
    router = APIRouter(prefix="", tags=["admin"])
    deps = default_deps()
    admin_service = AdminService(
        clients_repo=deps.clients,
        platform_profiles_repo=deps.platform_profiles,
        skills_repo=deps.skills,
        llm_provider_configs_repo=deps.llm_provider_configs,
    )
    loop_maintenance_service = LoopMaintenanceService(deps=deps)

    class ClientCreateRequest(BaseModel):
        id: str = Field(..., min_length=1)
        name: str = Field(..., min_length=1)
        metadata: Dict[str, Any] = Field(default_factory=dict)
        user_id: Optional[str] = None

    class BrandCreateRequest(BaseModel):
        id: str = Field(..., min_length=1)
        name: str = Field(..., min_length=1)
        metadata: Dict[str, Any] = Field(default_factory=dict)
        user_id: Optional[str] = None

    class ProductCreateRequest(BaseModel):
        id: str = Field(..., min_length=1)
        name: str = Field(..., min_length=1)
        description: Optional[str] = None
        metadata: Dict[str, Any] = Field(default_factory=dict)
        user_id: Optional[str] = None

    class ProductUpdateRequest(BaseModel):
        user_id: Optional[str] = None
        name: Optional[str] = None
        description: Optional[str] = None
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class ProductCanonicalAutofillRequest(BaseModel):
        user_id: Optional[str] = None
        mode: str = Field(default="preview", pattern="^(preview|apply)$")
        source_priority: Optional[list[str]] = None

    class ClientUserCreateRequest(BaseModel):
        user_id: Optional[str] = None
        member_user_id: str = Field(..., min_length=1)
        role: Optional[str] = None

    class PlatformProfileUpdateRequest(BaseModel):
        user_id: Optional[str] = None
        name: str = Field(..., min_length=1)
        version: str = Field(..., min_length=1)
        profile: Dict[str, Any] = Field(default_factory=dict)

    class SkillUpdateRequest(BaseModel):
        user_id: Optional[str] = None
        name: str = Field(..., min_length=1)
        description: str = Field(..., min_length=1)
        version: str = Field(..., min_length=1)
        content: str = Field(..., min_length=1)
        enabled: bool = True
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class SkillHistoryResponse(BaseModel):
        history: list[Dict[str, Any]]

    class LLMProviderConfigRequest(BaseModel):
        user_id: Optional[str] = None
        api_key: Optional[str] = None
        validation_api_key: Optional[str] = None
        model: Optional[str] = None
        validation_model: Optional[str] = None
        activate: Optional[bool] = None

    class LLMProviderActivateRequest(BaseModel):
        user_id: Optional[str] = None
        provider: str = Field(..., min_length=1)
        model: Optional[str] = None

    class LoopMaintenanceRunRequest(BaseModel):
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        lookback_days: int = Field(default=30, ge=1, le=365)
        min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    class LoopMaintenanceHistoryResponse(BaseModel):
        runs: list[Dict[str, Any]]

    @router.post("/clients")
    def create_client(payload: ClientCreateRequest) -> Dict[str, Any]:
        require_admin(payload.user_id)
        client = admin_service.create_client(
            client_id=payload.id, name=payload.name, metadata=payload.metadata
        )
        return {"client": client}

    @router.get("/clients")
    def list_clients(user_id: Optional[str] = None) -> Dict[str, Any]:
        require_admin(user_id)
        return {"clients": admin_service.list_clients()}

    @router.post("/clients/{client_id}/brands")
    def create_brand(client_id: str, payload: BrandCreateRequest) -> Dict[str, Any]:
        require_admin(payload.user_id)
        brand = admin_service.create_brand(
            brand_id=payload.id,
            client_id=client_id,
            name=payload.name,
            metadata=payload.metadata,
        )
        return {"brand": brand}

    @router.get("/clients/{client_id}/brands")
    def list_brands(client_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        require_admin(user_id)
        return {"brands": admin_service.list_brands(client_id=client_id)}

    @router.post("/brands/{brand_id}/products")
    def create_product(brand_id: str, payload: ProductCreateRequest) -> Dict[str, Any]:
        require_admin(payload.user_id)
        product = admin_service.create_product(
            product_id=payload.id,
            brand_id=brand_id,
            name=payload.name,
            description=payload.description,
            metadata=payload.metadata,
        )
        return {"product": product}

    @router.get("/brands/{brand_id}/products")
    def list_products(brand_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        require_admin(user_id)
        return {"products": admin_service.list_products(brand_id=brand_id)}

    @router.put("/brands/{brand_id}/products/{product_id}")
    def update_product(
        brand_id: str,
        product_id: str,
        payload: ProductUpdateRequest,
    ) -> Dict[str, Any]:
        require_admin(payload.user_id)
        product = admin_service.update_product(
            product_id=product_id,
            name=payload.name,
            description=payload.description,
            metadata=payload.metadata,
        )
        return {"product": product}

    @router.post("/brands/{brand_id}/products/{product_id}/canonical-spec/autofill")
    def autofill_product_canonical_spec(
        brand_id: str,
        product_id: str,
        payload: ProductCanonicalAutofillRequest,
    ) -> Dict[str, Any]:
        require_admin(payload.user_id)
        try:
            result = admin_service.autofill_product_canonical_spec(
                product_id=product_id,
                source_priority=payload.source_priority,
                apply=payload.mode == "apply",
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"result": result}

    @router.post("/clients/{client_id}/users")
    def add_client_user(
        client_id: str, payload: ClientUserCreateRequest
    ) -> Dict[str, Any]:
        require_admin(payload.user_id)
        mapping = admin_service.add_client_user(
            client_id=client_id,
            member_user_id=payload.member_user_id,
            role=payload.role,
        )
        return {"user": mapping}

    @router.get("/clients/{client_id}/users")
    def list_client_users(
        client_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        require_admin(user_id)
        return {"users": admin_service.list_client_users(client_id=client_id)}

    @router.get("/platform-profile")
    def get_platform_profile(user_id: Optional[str] = None) -> Dict[str, Any]:
        require_admin(user_id)
        profile = admin_service.get_platform_profile()
        return {"profile": profile}

    @router.put("/platform-profile")
    def update_platform_profile(
        payload: PlatformProfileUpdateRequest,
    ) -> Dict[str, Any]:
        require_admin(payload.user_id)
        profile = admin_service.update_platform_profile(
            name=payload.name, version=payload.version, profile=payload.profile
        )
        return {"profile": profile}

    @router.get("/skills/{skill_name}")
    def get_skill(skill_name: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        require_admin(user_id)
        skill = admin_service.get_skill(name=skill_name)
        return {"skill": skill}

    @router.put("/skills/{skill_name}")
    def update_skill(skill_name: str, payload: SkillUpdateRequest) -> Dict[str, Any]:
        require_admin(payload.user_id)
        skill = admin_service.update_skill(
            name=skill_name,
            description=payload.description,
            version=payload.version,
            content=payload.content,
            enabled=payload.enabled,
            metadata=payload.metadata,
        )
        return {"skill": skill}

    @router.get("/skills/{skill_name}/history")
    def list_skill_history(
        skill_name: str, user_id: Optional[str] = None, limit: int = 10
    ) -> Dict[str, Any]:
        require_admin(user_id)
        history = admin_service.list_skill_history(name=skill_name, limit=limit)
        return {"history": history}

    @router.get("/llm/config")
    def list_llm_configs(user_id: Optional[str] = None) -> Dict[str, Any]:
        require_admin(user_id)
        configs = admin_service.list_llm_provider_configs()
        summary = admin_service.get_llm_provider_summary()
        providers = summary.get("providers", {})
        sanitized = []
        for item in configs:
            provider = item.get("provider")
            provider_summary = providers.get(provider, {})
            sanitized.append(
                {
                    "provider": provider,
                    "configured": provider_summary.get("configured", False),
                    "model": provider_summary.get("model"),
                    "validation_model": provider_summary.get("validation_model"),
                    "is_active": provider_summary.get("is_active", False),
                    "updated_at": item.get("updated_at"),
                }
            )
        return {
            "active_provider": summary.get("active_provider"),
            "providers": providers,
            "configs": sanitized,
        }

    @router.put("/llm/config/{provider}")
    def update_llm_config(
        provider: str, payload: LLMProviderConfigRequest
    ) -> Dict[str, Any]:
        require_admin(payload.user_id)
        config = admin_service.update_llm_provider_config(
            provider=provider,
            api_key=payload.api_key,
            validation_api_key=payload.validation_api_key,
            model=payload.model,
            validation_model=payload.validation_model,
            activate=payload.activate,
            updated_by=payload.user_id,
        )
        summary = admin_service.get_llm_provider_summary()
        return {"config": config, "summary": summary}

    @router.post("/llm/config/activate")
    def activate_llm_provider(payload: LLMProviderActivateRequest) -> Dict[str, Any]:
        require_admin(payload.user_id)
        config = admin_service.set_active_llm_provider(
            provider=payload.provider, model=payload.model, updated_by=payload.user_id
        )
        summary = admin_service.get_llm_provider_summary()
        return {"config": config, "summary": summary}

    @router.post("/ops/loop-maintenance")
    def run_loop_maintenance(payload: LoopMaintenanceRunRequest) -> Dict[str, Any]:
        require_admin(payload.user_id)
        target_client_ids = (
            [payload.client_id]
            if payload.client_id
            else [item["id"] for item in deps.clients.list_clients()]
        )
        results: list[Dict[str, Any]] = []
        for target_client_id in target_client_ids:
            calibration = loop_maintenance_service.refresh_calibration_profiles(
                client_id=target_client_id,
                lookback_days=payload.lookback_days,
            )
            distilled = loop_maintenance_service.distill_recent_beliefs(
                client_id=target_client_id,
                min_confidence=payload.min_confidence,
            )
            results.append(
                {
                    "client_id": target_client_id,
                    "calibration_profiles_updated": len(calibration),
                    "memory_artifacts_distilled": len(distilled),
                }
            )
            deps.loop_maintenance_runs.create_run(
                client_id=target_client_id,
                lookback_days=payload.lookback_days,
                min_confidence=payload.min_confidence,
                calibration_profiles_updated=len(calibration),
                memory_artifacts_distilled=len(distilled),
                triggered_by=payload.user_id,
            )
        history_client_id = payload.client_id or (
            target_client_ids[0] if target_client_ids else None
        )
        history = (
            deps.loop_maintenance_runs.list_runs(client_id=history_client_id, limit=20)
            if history_client_id
            else []
        )
        return {
            "results": results,
            "lookback_days": payload.lookback_days,
            "min_confidence": payload.min_confidence,
            "history": history,
        }

    @router.get("/ops/loop-maintenance/history")
    def list_loop_maintenance_runs(
        user_id: Optional[str] = None,
        client_id: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        require_admin(user_id)
        if not client_id:
            raise HTTPException(status_code=400, detail="client_id is required")
        return {
            "runs": deps.loop_maintenance_runs.list_runs(
                client_id=client_id, limit=max(1, min(100, int(limit)))
            )
        }
else:  # pragma: no cover
    router = None


__all__ = ["router"]
