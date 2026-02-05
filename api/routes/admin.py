from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, HTTPException
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from api.utils.tenancy import require_admin
from application.services.admin_service import AdminService
from api.composition import default_deps

if APIRouter:
    router = APIRouter(prefix="", tags=["admin"])
    deps = default_deps()
    admin_service = AdminService(
        clients_repo=deps.clients,
        platform_profiles_repo=deps.platform_profiles,
        skills_repo=deps.skills,
    )

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
else:  # pragma: no cover
    router = None


__all__ = ["router"]
