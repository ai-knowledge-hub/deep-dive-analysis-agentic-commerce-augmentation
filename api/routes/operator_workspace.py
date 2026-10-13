"""Primary workspace on the shared operator conversation API boundary."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field
from api.composition import default_deps
from api.runtime_composition import default_completion_coordinator
from api.utils.operator_workspace_session import resolve_workspace_identity
from api.utils.operator_workspace_registry import current_registry
from api.utils.agent_run_authorization import principal_has_scope
from api.utils.principals import _assert_principal_is_active, ensure_principal
from api.utils.tenancy import require_client_role
from application.ports.deps import AppDeps
from application.services.conversation.operator_gateway import (
    OperatorConversationService,
)
from application.services.conversation.operator_workspace import (
    open_workspace,
    require_workspace,
    confirm_creation,
    prepare_creation,
)


def _deps():
    return default_deps()


def _completion_coordinator(deps: AppDeps = Depends(_deps)):
    return default_completion_coordinator(deps)


router = APIRouter(prefix="/conversation/operator/workspaces", tags=["conversation"])


class WorkspaceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str | None = None
    session_id: str | None = None
    experiment_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)


class CreationConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str | None = None
    proposal_digest: str = Field(min_length=64, max_length=64)


class OpenRunConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str | None = None
    run_id: str


def authorize(principal, *, write=False):
    scope = "agent_runs:write" if write else "agent_runs:read"
    if not principal_has_scope(principal=principal, scope=scope):
        raise HTTPException(403, f"Missing required scope: {scope}")
    require_client_role(
        client_id=principal.client_id,
        user_id=principal.principal_id.removeprefix("human:"),
        allowed_roles={"owner", "admin", "operator"}
        if write
        else {"owner", "admin", "operator", "analyst"},
    )
    _assert_principal_is_active(
        principal_id=principal.principal_id,
        principal_type="human",
        tenant_id=principal.client_id,
    )


def context(request, *, client_id, session_id, operation, **kwargs):
    principal = resolve_workspace_identity(
        request=request,
        client_id=client_id,
        session_id=session_id,
        operation=operation,
        **kwargs,
    )
    authorize(principal, write=operation == "confirm")
    ensure_principal(
        principal_id=principal.principal_id,
        principal_type="human",
        tenant_id=principal.client_id,
        display_name=principal.principal_id.removeprefix("human:"),
        metadata={"auth_method": principal.auth_method},
    )
    return principal


@router.post("/message")
def message(
    payload: WorkspaceMessage,
    request: Request,
    deps: AppDeps = Depends(_deps),
    coordinator=Depends(_completion_coordinator),
):
    principal = context(
        request,
        client_id=payload.client_id,
        session_id=payload.session_id or "new",
        operation="message",
    )
    try:
        workspace = open_workspace(
            deps,
            tenant_id=principal.client_id,
            principal_id=principal.principal_id,
            session_id=payload.session_id,
        )
        if workspace["run_id"]:
            run = deps.agent_runs.get_agent_run(
                run_id=workspace["run_id"], client_id=principal.client_id
            )
            if not run or (
                principal.auth_method == "bearer_token"
                and run["principal_id"] != principal.principal_id
                and not principal_has_scope(
                    principal=principal, scope="agent_runs:supervise"
                )
            ):
                raise HTTPException(403, "Run supervision is unavailable")
            result = OperatorConversationService(
                deps=deps, completion_reader=coordinator.get_completion_read_model
            ).respond(
                tenant_id=principal.client_id,
                principal_id=principal.principal_id,
                session_user_id=principal.principal_id.removeprefix("human:"),
                run_id=workspace["run_id"],
                message=payload.message,
                session_id=workspace["session_id"],
            )
            return {
                "state": "supervision",
                "session_id": workspace["session_id"],
                "run_id": workspace["run_id"],
                "response": result,
            }
        service = OperatorConversationService(
            deps=deps, completion_reader=coordinator.get_completion_read_model
        )
        result = service.prepare_objective(
            prepare=prepare_creation,
            workspace=workspace,
            message=payload.message,
            experiment_id=payload.experiment_id,
            registry=lambda: current_registry(principal.client_id),
        )
        deps.turns.add_turn(
            session_id=workspace["session_id"], speaker="user", content=payload.message
        )
        deps.turns.add_turn(
            session_id=workspace["session_id"],
            speaker="agent",
            content=result["answer"],
            metadata={"workspace_result": result},
        )
        return {**result, "session_id": workspace["session_id"], "run_id": None}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{session_id}")
def history(
    session_id: str,
    request: Request,
    client_id: str | None = None,
    before_turn_id: int | None = Query(default=None, gt=0, le=9007199254740991),
    deps: AppDeps = Depends(_deps),
):
    principal = context(
        request, client_id=client_id, session_id=session_id, operation="read"
    )
    try:
        workspace = require_workspace(
            deps,
            tenant_id=principal.client_id,
            principal_id=principal.principal_id,
            session_id=session_id,
        )
        records = deps.operator_workspace.history(
            session_id=session_id,
            tenant_id=principal.client_id,
            principal_id=principal.principal_id,
        )
        turns = deps.turns.list_recent_turns(
            session_id=session_id, limit=501, before_id=before_turn_id
        )
        chronological_turns = list(reversed(turns[:500]))
        run = (
            deps.agent_runs.get_agent_run(
                run_id=workspace["run_id"], client_id=principal.client_id
            )
            if workspace["run_id"]
            else None
        )
        if workspace["run_id"] and (
            not run
            or (
                principal.auth_method == "bearer_token"
                and run["principal_id"] != principal.principal_id
                and not principal_has_scope(
                    principal=principal, scope="agent_runs:supervise"
                )
            )
        ):
            raise HTTPException(403, "Run supervision is unavailable")
        actions = (
            deps.agent_actions.list_agent_actions(
                agent_run_id=workspace["run_id"], limit=501
            )
            if run
            else []
        )
        events = (
            deps.agent_events.list_agent_events(
                agent_run_id=workspace["run_id"], limit=201
            )
            if run
            else []
        )
        return {
            **workspace,
            **records,
            "run": run,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "actions": actions[:500],
            "actions_has_more": len(actions) > 500,
            "events": events[:200],
            "events_has_more": len(events) > 200,
            "turns": chronological_turns,
            "turns_has_more": len(turns) > 500,
            "turns_before_id": chronological_turns[0]["id"]
            if len(turns) > 500 else None,
        }
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{session_id}/proposals/{proposal_id}/confirm")
def confirm(
    session_id: str,
    proposal_id: str,
    payload: CreationConfirmation,
    request: Request,
    deps: AppDeps = Depends(_deps),
    coordinator=Depends(_completion_coordinator),
):
    principal = context(
        request,
        client_id=payload.client_id,
        session_id=session_id,
        operation="confirm",
        proposal_id=proposal_id,
        proposal_digest=payload.proposal_digest,
    )
    try:
        require_workspace(
            deps,
            tenant_id=principal.client_id,
            principal_id=principal.principal_id,
            session_id=session_id,
        )
        proposal = deps.operator_workspace.get_proposal(
            proposal_id=proposal_id,
            session_id=session_id,
            tenant_id=principal.client_id,
            principal_id=principal.principal_id,
        )
        if not proposal:
            raise LookupError("Creation proposal not found")
        if proposal["proposal_digest"] != payload.proposal_digest:
            raise ValueError("Creation proposal digest does not match")
        receipt = confirm_creation(
            deps,
            proposal=proposal,
            authorize=lambda: authorize(principal, write=True),
            registry=lambda: current_registry(principal.client_id),
            coordinator=coordinator,
        )
        return {
            "receipt": receipt,
            "session_id": session_id,
            "run_id": receipt["run_id"],
        }
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("")
def list_conversations(
    request: Request, client_id: str | None = None, deps: AppDeps = Depends(_deps)
):
    principal = context(
        request, client_id=client_id, session_id="list", operation="list"
    )
    return deps.operator_workspace.list_workspaces(
        tenant_id=principal.client_id, principal_id=principal.principal_id
    )


@router.post("/open")
def open_run(
    payload: OpenRunConversation, request: Request, deps: AppDeps = Depends(_deps)
):
    principal = context(
        request,
        client_id=payload.client_id,
        session_id=payload.run_id,
        operation="open",
    )
    run = deps.agent_runs.get_agent_run(
        run_id=payload.run_id, client_id=principal.client_id
    )
    if not run or (
        principal.auth_method == "bearer_token"
        and run["principal_id"] != principal.principal_id
        and not principal_has_scope(principal=principal, scope="agent_runs:supervise")
    ):
        raise HTTPException(404, "Run unavailable")
    deps.users.ensure_user(principal.principal_id.removeprefix("human:"))
    session = deps.sessions.create_session(
        user_id=principal.principal_id.removeprefix("human:"),
        client_id=principal.client_id,
        state={
            "conversation_kind": "operator_run",
            "workspace": True,
            "run_id": run["id"],
        },
    )
    deps.operator_workspace.register_workspace(
        session_id=session["id"],
        tenant_id=principal.client_id,
        principal_id=principal.principal_id,
        run_id=run["id"],
    )
    return {"session_id": session["id"], "run_id": run["id"]}
