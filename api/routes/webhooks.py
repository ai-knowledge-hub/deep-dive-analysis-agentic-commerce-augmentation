from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, Request
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore
    Request = Any  # type: ignore

from shared.config.env import settings
from infrastructure.db import users as users_repo


def _raise_http(status_code: int, detail: str) -> None:
    if APIRouter:
        from fastapi import HTTPException

        raise HTTPException(status_code=status_code, detail=detail)
    raise Exception(detail)


def _primary_email(data: Dict[str, Any]) -> Optional[str]:
    primary_id = data.get("primary_email_address_id")
    for entry in data.get("email_addresses") or []:
        if primary_id and entry.get("id") == primary_id:
            return entry.get("email_address")
    if data.get("email_addresses"):
        return data["email_addresses"][0].get("email_address")
    return None


def _user_metadata(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    full_name = " ".join([name for name in [first_name, last_name] if name])
    return {
        "clerk_event": event_type,
        "clerk_user_id": data.get("id"),
        "email": _primary_email(data),
        "username": data.get("username"),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name or None,
        "image_url": data.get("image_url"),
        "last_sign_in_at": data.get("last_sign_in_at"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


if APIRouter:
    router = APIRouter(prefix="/webhooks", tags=["webhooks"])

    @router.post("/clerk")
    async def clerk_webhook(request: Request) -> Dict[str, str]:
        secret = settings.clerk_webhook_secret
        if not secret:
            _raise_http(400, "CLERK_WEBHOOK_SECRET not set")

        headers = {
            "svix-id": request.headers.get("svix-id"),
            "svix-timestamp": request.headers.get("svix-timestamp"),
            "svix-signature": request.headers.get("svix-signature"),
        }
        if not all(headers.values()):
            _raise_http(400, "Missing webhook headers")

        payload = await request.body()
        try:
            from svix import Webhook, WebhookVerificationError
        except ImportError as exc:  # pragma: no cover
            _raise_http(500, "svix is required for webhook verification")
            raise exc

        try:
            event = Webhook(secret).verify(payload.decode("utf-8"), headers)
        except WebhookVerificationError as exc:
            _raise_http(400, "Invalid webhook signature")
            raise exc

        if isinstance(event, str):
            event = json.loads(event)

        event_type = event.get("type") or ""
        data = event.get("data") or {}
        user_id = data.get("id")
        if not user_id:
            return {"status": "ignored"}

        users_repo.ensure_user(user_id)
        if event_type in {"user.created", "user.updated"}:
            users_repo.update_metadata(
                user_id, metadata=_user_metadata(event_type, data)
            )
        elif event_type == "user.deleted":
            users_repo.update_metadata(
                user_id, metadata={"clerk_event": event_type, "clerk_deleted": True}
            )
        return {"status": "ok"}
else:  # pragma: no cover
    router = None


__all__ = ["router"]
