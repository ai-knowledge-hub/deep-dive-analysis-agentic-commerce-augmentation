from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from api.utils.tenancy import require_admin
from application.services.admin_service import AdminService
from api.composition import default_deps

if APIRouter:
    router = APIRouter(prefix="", tags=["admin"])
    admin_service = AdminService(clients_repo=default_deps().clients)

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

    class ClientUserCreateRequest(BaseModel):
        user_id: Optional[str] = None
        member_user_id: str = Field(..., min_length=1)
        role: Optional[str] = None

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
else:  # pragma: no cover
    router = None


__all__ = ["router"]
