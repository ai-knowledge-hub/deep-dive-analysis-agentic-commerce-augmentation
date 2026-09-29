"""Read-only operator conversation routes grounded in one authorized run."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from api.composition import default_deps
from api.runtime_composition import default_completion_coordinator
from api.utils.agent_run_authorization import principal_has_scope
from api.utils.operator_session import resolve_operator_session_identity
from api.utils.principals import PrincipalContext, ensure_principal
from api.utils.tenancy import require_client_role
from application.ports.deps import AppDeps
from application.services.conversation.operator_gateway import (
    OperatorConversationError,
    OperatorConversationService,
)
from application.services.workflow_outcomes.production import (
    SequentialCompletionCoordinator,
)


router = APIRouter(prefix="/conversation/operator", tags=["conversation"])


class OperatorMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=2_000)
    user_id: str | None = None
    client_id: str | None = None
    session_id: str | None = None


def _deps() -> AppDeps:
    return default_deps()


def _completion_coordinator(
    deps: AppDeps = Depends(_deps),
) -> SequentialCompletionCoordinator:
    return default_completion_coordinator(deps)


def _authorized_context(
    *,
    request: Request,
    payload: OperatorMessageRequest,
    run_id: str,
    deps: AppDeps,
) -> tuple[PrincipalContext, dict[str, Any]]:
    identity = resolve_operator_session_identity(
        request=request,
        client_id=payload.client_id,
        user_id=payload.user_id,
        run_id=run_id,
    )
    principal = identity.principal
    authenticated_user_id = identity.user_id
    if not principal_has_scope(principal=principal, scope="agent_runs:read"):
        raise HTTPException(
            status_code=403,
            detail="Missing required scope: agent_runs:read",
        )
    require_client_role(
        client_id=principal.client_id,
        user_id=authenticated_user_id,
        allowed_roles={"owner", "admin", "operator", "analyst"},
    )
    ensure_principal(
        principal_id=principal.principal_id,
        principal_type="human",
        tenant_id=principal.client_id,
        display_name=authenticated_user_id,
        metadata={
            "auth_method": principal.auth_method,
            "user_id": authenticated_user_id,
        },
    )
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=principal.client_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return principal, run


def _respond(
    *,
    request: Request,
    payload: OperatorMessageRequest,
    run_id: str,
    deps: AppDeps,
    coordinator: SequentialCompletionCoordinator,
) -> dict[str, Any]:
    principal, _ = _authorized_context(
        request=request, payload=payload, run_id=run_id, deps=deps
    )
    session_user_id = _human_user_id(principal.principal_id)
    service = OperatorConversationService(
        deps=deps,
        completion_reader=coordinator.get_completion_read_model,
    )
    try:
        return service.respond(
            tenant_id=principal.client_id,
            principal_id=principal.principal_id,
            session_user_id=session_user_id,
            run_id=run_id,
            message=payload.message,
            session_id=payload.session_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc
    except OperatorConversationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _human_user_id(principal_id: str) -> str:
    return str(principal_id).strip().removeprefix("human:")


@router.post("/runs/{run_id}/message")
def send_operator_message(
    run_id: str,
    payload: OperatorMessageRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
    coordinator: SequentialCompletionCoordinator = Depends(_completion_coordinator),
) -> dict[str, Any]:
    return _respond(
        request=request,
        payload=payload,
        run_id=run_id,
        deps=deps,
        coordinator=coordinator,
    )


@router.post("/runs/{run_id}/stream")
def stream_operator_message(
    run_id: str,
    payload: OperatorMessageRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
    coordinator: SequentialCompletionCoordinator = Depends(_completion_coordinator),
) -> StreamingResponse:
    # Authorize before opening the stream so cross-scope callers receive an HTTP error.
    _authorized_context(request=request, payload=payload, run_id=run_id, deps=deps)

    def event_stream():
        yield _sse({"phase": "building_verified_snapshot"}, "status")
        response = _respond(
            request=request,
            payload=payload,
            run_id=run_id,
            deps=deps,
            coordinator=coordinator,
        )
        for chunk in _chunks(str(response["answer"])):
            yield _sse({"content": chunk}, "delta")
        yield _sse({"phase": "complete"}, "status")
        yield _sse(response, "operator_conversation")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(payload: dict[str, Any], event: str) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _chunks(text: str, size: int = 32) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


__all__ = ["router"]
