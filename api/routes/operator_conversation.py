"""Grounded operator conversation and explicitly confirmed scoped commands."""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from api.composition import default_deps
from api.runtime_composition import default_completion_coordinator, default_runtime
from api.utils.agent_run_authorization import principal_has_scope
from api.utils.operator_command_session import resolve_operator_command_identity
from api.utils.operator_session import resolve_operator_session_identity
from api.utils.principals import PrincipalContext, ensure_principal
from api.utils.tenancy import require_client_role
from application.ports.deps import AppDeps
from application.services.conversation.operator_gateway import (
    OperatorConversationError,
    OperatorConversationService,
)
from application.services.conversation.operator_commands import (
    conversational_pause_preflight,
    operator_proposal_view,
)
from application.services.conversation.operator_resume import (
    build_resume_snapshot,
    conversational_resume_preflight,
)
from application.services.conversation.operator_snapshot import build_operator_snapshot
from application.services.conversation.operator_cancel import (
    build_cancel_snapshot,
    conversational_cancel_preflight,
)
from application.services.agent_runtime.commands import (
    AgentRunCommandError,
    issue_agent_run_command as issue_agent_run_command_service,
)
from application.services.agent_runtime.runtime import AgentRuntimeService
from domain.workflow.operator_commands import (
    OperatorCommandConflictError,
    OperatorCommandCursorError,
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


class OperatorCommandConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal["pause", "resume", "cancel"] = "pause"
    proposal_digest: str = Field(..., min_length=64, max_length=64)
    user_id: str | None = None
    client_id: str | None = None


def _authorize_run_read(
    *,
    request: Request,
    run_id: str,
    deps: AppDeps,
    client_id: str | None,
    user_id: str | None,
) -> tuple[PrincipalContext, dict[str, Any]]:
    identity = resolve_operator_session_identity(
        request=request,
        client_id=client_id,
        user_id=user_id,
        run_id=run_id,
    )
    principal = identity.principal
    if not principal_has_scope(principal=principal, scope="agent_runs:read"):
        raise HTTPException(
            status_code=403,
            detail="Missing required scope: agent_runs:read",
        )
    require_client_role(
        client_id=principal.client_id,
        user_id=identity.user_id,
        allowed_roles={"owner", "admin", "operator", "analyst"},
    )
    ensure_principal(
        principal_id=principal.principal_id,
        principal_type="human",
        tenant_id=principal.client_id,
        display_name=identity.user_id,
        metadata={
            "auth_method": principal.auth_method,
            "user_id": identity.user_id,
        },
    )
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=principal.client_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return principal, run


def _deps() -> AppDeps:
    return default_deps()


def _completion_coordinator(
    deps: AppDeps = Depends(_deps),
) -> SequentialCompletionCoordinator:
    return default_completion_coordinator(deps)


def _runtime(deps: AppDeps = Depends(_deps)) -> AgentRuntimeService:
    return default_runtime(deps)


def _authorized_context(
    *,
    request: Request,
    payload: OperatorMessageRequest,
    run_id: str,
    deps: AppDeps,
) -> tuple[PrincipalContext, dict[str, Any]]:
    return _authorize_run_read(
        request=request,
        deps=deps,
        run_id=run_id,
        client_id=payload.client_id,
        user_id=payload.user_id,
    )


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


@router.get("/runs/{run_id}/commands")
def list_operator_commands(
    run_id: str,
    request: Request,
    client_id: str | None = None,
    user_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
    deps: AppDeps = Depends(_deps),
) -> dict[str, Any]:
    principal, _ = _authorize_run_read(
        request=request,
        run_id=run_id,
        deps=deps,
        client_id=client_id,
        user_id=user_id,
    )
    try:
        page_result = deps.operator_commands.list_records(
            tenant_id=principal.client_id,
            workflow_id=run_id,
            limit=limit,
            cursor=cursor,
        )
    except OperatorCommandCursorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    records = page_result["records"]
    page = page_result["page"]
    return {
        "contract": "operator-command-record-list.v1",
        "run_id": run_id,
        "records": [
            {
                "proposal": operator_proposal_view(record["proposal"]),
                "receipt": record["receipt"],
            }
            for record in records
        ],
        "count": len(records),
        "total_count": page["total_count"],
        "page": page,
        "completeness": {
            "state": "partial"
            if cursor is not None or page["has_more"]
            else "complete",
            "included_count": len(records),
            "total_count": page["total_count"],
            "reason": (
                "additional_pages_available"
                if page["has_more"]
                else "continuation_page"
                if cursor is not None
                else None
            ),
        },
    }


@router.post("/runs/{run_id}/commands/{proposal_id}/confirm")
def confirm_operator_command(
    run_id: str,
    proposal_id: str,
    payload: OperatorCommandConfirmationRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
    runtime: AgentRuntimeService = Depends(_runtime),
    coordinator: SequentialCompletionCoordinator = Depends(_completion_coordinator),
) -> dict[str, Any]:
    identity = resolve_operator_command_identity(
        request=request,
        client_id=payload.client_id,
        user_id=payload.user_id,
        run_id=run_id,
        proposal_id=proposal_id,
        proposal_digest=payload.proposal_digest,
        command_type=payload.command_type,
    )
    principal = identity.principal
    if not (
        principal_has_scope(principal=principal, scope="operator_commands:confirm")
        or principal_has_scope(principal=principal, scope="agent_runs:write")
    ):
        raise HTTPException(
            status_code=403,
            detail="Missing required scope: operator_commands:confirm",
        )
    require_client_role(
        client_id=principal.client_id,
        user_id=identity.user_id,
        allowed_roles={"owner", "admin", "operator"},
    )
    ensure_principal(
        principal_id=principal.principal_id,
        principal_type="human",
        tenant_id=principal.client_id,
        display_name=identity.user_id,
        metadata={
            "auth_method": principal.auth_method,
            "user_id": identity.user_id,
            "scopes": list(principal.scopes),
        },
    )
    proposal = deps.operator_commands.get_proposal(
        proposal_id=proposal_id,
        tenant_id=principal.client_id,
        workflow_id=run_id,
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Command proposal not found")
    if proposal["command_type"] != payload.command_type:
        raise HTTPException(
            status_code=409, detail="Command type does not match the exact proposal"
        )
    if proposal["proposal_digest"] != payload.proposal_digest:
        raise HTTPException(status_code=409, detail="Command proposal digest changed")
    if proposal["principal_id"] != principal.principal_id:
        raise HTTPException(
            status_code=403, detail="Command proposal belongs to a different operator"
        )

    existing_receipt = deps.operator_commands.get_receipt(
        proposal_id=proposal_id,
        tenant_id=principal.client_id,
        workflow_id=run_id,
    )
    if existing_receipt is not None:
        replayed_run = deps.agent_runs.get_agent_run(
            run_id=run_id, client_id=principal.client_id
        )
        if replayed_run is None:
            raise HTTPException(status_code=404, detail="Agent run not found")
        return {
            "contract": "operator-command-confirmation.v1",
            "run_id": run_id,
            "proposal_id": proposal_id,
            "command": {
                "id": existing_receipt["event_ids"]["command"],
                "event_type": f"operator_command_{existing_receipt['command_type']}",
                "status": "completed",
                "anchors": {
                    "proposal_id": proposal_id,
                    "proposal_digest": proposal["proposal_digest"],
                    "receipt_id": existing_receipt["receipt_id"],
                },
            },
            "receipt": existing_receipt,
            "run": replayed_run,
        }

    snapshot_builder = (
        build_cancel_snapshot
        if payload.command_type == "cancel"
        else build_resume_snapshot
        if payload.command_type == "resume"
        else build_operator_snapshot
    )
    preflight_builder = (
        conversational_cancel_preflight
        if payload.command_type == "cancel"
        else conversational_resume_preflight
        if payload.command_type == "resume"
        else conversational_pause_preflight
    )
    snapshot = snapshot_builder(
        deps=deps,
        completion_reader=coordinator.get_completion_read_model,
        tenant_id=principal.client_id,
        principal_id=principal.principal_id,
        run_id=run_id,
    )
    # The transaction owns rejection as well as replay. A competing exact
    # confirmation may commit after the early read and before this lock.
    preflight = preflight_builder(
        deps=deps,
        tenant_id=principal.client_id,
        run_id=run_id,
        **(
            {"snapshot": snapshot}
            if payload.command_type in {"resume", "cancel"}
            else {}
        ),
    )

    def confirmation_state() -> dict[str, Any]:
        require_client_role(
            client_id=principal.client_id,
            user_id=identity.user_id,
            allowed_roles={"owner", "admin", "operator"},
        )
        current_snapshot = snapshot_builder(
            deps=deps,
            completion_reader=coordinator.get_completion_read_model,
            tenant_id=principal.client_id,
            principal_id=principal.principal_id,
            run_id=run_id,
        )
        current_preflight = preflight_builder(
            deps=deps,
            tenant_id=principal.client_id,
            run_id=run_id,
            **(
                {"snapshot": current_snapshot}
                if payload.command_type in {"resume", "cancel"}
                else {}
            ),
        )
        return {
            "snapshot_digest": current_snapshot["snapshot_digest"],
            "preflight": current_preflight,
        }

    try:
        result = issue_agent_run_command_service(
            deps=deps,
            runtime=runtime,
            run_id=run_id,
            client_id=principal.client_id,
            user_id=identity.user_id,
            command_type="start"
            if payload.command_type == "resume"
            else payload.command_type,
            action_id=None,
            message="Confirmed from operator conversation",
            metadata={"origin": "operator_conversation", "proposal_id": proposal_id},
            idempotency_key=proposal["idempotency_key"],
            conversation_proposal=proposal,
            conversation_preflight=preflight,
            conversation_principal_id=principal.principal_id,
            conversation_confirmation_state=confirmation_state,
        )
    except OperatorCommandConflictError as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "message": exc.message}
        ) from exc
    except AgentRunCommandError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {
        "contract": "operator-command-confirmation.v1",
        "run_id": run_id,
        "proposal_id": proposal_id,
        "command": result["command"],
        "receipt": result["command_receipt"],
        "run": result["run"],
    }


def _sse(payload: dict[str, Any], event: str) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _chunks(text: str, size: int = 32) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


__all__ = ["router"]
