from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps

router = APIRouter(prefix="/copy-revisions", tags=["copy-revisions"])


def _deps() -> AppDeps:
    return default_deps()


class CreateRevisionRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    source_id: Optional[str] = None
    source_variant_id: Optional[str] = None
    base_description: str = Field(..., min_length=1)
    candidate_description: str = Field(..., min_length=1)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublishRevisionRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("")
def create_revision(payload: CreateRevisionRequest) -> Dict[str, Any]:
    deps = _deps()
    client_id = require_client_id(payload.client_id, payload.user_id)
    revision = deps.copy_revisions.create_revision(
        client_id=client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        source_variant_id=payload.source_variant_id,
        base_description=payload.base_description,
        candidate_description=payload.candidate_description,
        notes=payload.notes,
        metadata=payload.metadata,
        created_by=payload.user_id,
    )
    return {"revision": revision}


@router.get("")
def list_revisions(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    product_id: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    deps = _deps()
    scoped_client_id = require_client_id(client_id, user_id)
    revisions = deps.copy_revisions.list_revisions(
        client_id=scoped_client_id,
        product_id=product_id,
        source_type=source_type,
        status=status,
        limit=limit,
    )
    return {"revisions": revisions}


@router.get("/{revision_id}")
def get_revision(
    revision_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    deps = _deps()
    scoped_client_id = require_client_id(client_id, user_id)
    revision = deps.copy_revisions.get_revision(revision_id=revision_id)
    if not revision or revision.get("client_id") != scoped_client_id:
        raise HTTPException(status_code=404, detail="Copy revision not found")
    return {"revision": revision}


@router.post("/{revision_id}/publish")
def publish_revision(
    revision_id: str,
    payload: PublishRevisionRequest,
) -> Dict[str, Any]:
    deps = _deps()
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    revision = deps.copy_revisions.get_revision(revision_id=revision_id)
    if not revision or revision.get("client_id") != scoped_client_id:
        raise HTTPException(status_code=404, detail="Copy revision not found")

    product = deps.clients.get_product_for_client(
        client_id=scoped_client_id, product_id=revision["product_id"]
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    metadata = dict(product.get("metadata") or {})
    copy_meta = dict(metadata.get("copy_revision") or {})
    copy_meta.update(
        {
            "latest_revision_id": revision["id"],
            "latest_revision_source": revision.get("source_type"),
            "published_at": revision.get("updated_at"),
        }
    )
    metadata["copy_revision"] = copy_meta

    updated_product = deps.clients.update_product(
        product_id=revision["product_id"],
        description=revision["candidate_description"],
        metadata=metadata,
    )
    updated_revision = deps.copy_revisions.update_revision_status(
        revision_id=revision_id,
        status="published",
        approved_by=payload.user_id,
        notes=payload.notes,
    )
    return {
        "revision": updated_revision,
        "product": updated_product,
    }
