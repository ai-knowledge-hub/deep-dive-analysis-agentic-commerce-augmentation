"""Conversation endpoints exposing session + discovery telemetry."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from application.agents.goal_clarification_agent import GoalClarificationAgent
from application.services.conversation.service import ConversationService
from application.services.conversation.agents import (
    CommerceAgent,
    ExplainAgent,
    IntentAgent,
)
from application.services.conversation.commerce_plan_builder import CommercePlanBuilder
from application.services.conversation.product_search import search_products_for_client
from application.services.conversation.context_builder import context_for
from infrastructure.llm.intent_classifier import (
    build_intent_classifier,
    log_intent_replay,
)
from infrastructure.llm.research_agent import run_research
from application.services.evidence.alignment_service import AlignmentService
from infrastructure.llm.gateway import chat
from infrastructure.llm.prompts import VALUES_CLARIFICATION_PROMPT
from infrastructure.llm.product_reasoner import reason_about_products_default
from domain.commerce.compare import compare as compare_products
from application.services.evidence.intentionality_profiler import build_profile
from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.ports.deps import AppDeps

router = APIRouter(prefix="/conversation", tags=["conversation"])

# Optional test override hooks (preserve compatibility with existing monkeypatch tests).
GOAL_AGENT: Any = None
INTENT_AGENT: Any = None
COMMERCE_AGENT: Any = None
EXPLAIN_AGENT: Any = None


def _deps() -> AppDeps:
    return default_deps()


def _alignment(deps: AppDeps) -> AlignmentService:
    return AlignmentService(deps)


def _build_profile_with_llm(product: Any, *, deps: AppDeps) -> Any:
    return build_profile(product, generate_fn=deps.generate)


def _search_products(
    *,
    deps: AppDeps,
    query: str,
    client_id: str | None,
    brand_id: str | None,
):
    if not client_id:
        return []
    return search_products_for_client(
        deps=deps, query=query, client_id=client_id, brand_id=brand_id
    )


def _intent_agent() -> IntentAgent:
    return IntentAgent(
        classifier=build_intent_classifier(),
        context_for_fn=context_for,
        log_replay_fn=log_intent_replay,
    )


def _goal_agent() -> GoalClarificationAgent:
    return GoalClarificationAgent(chat_fn=chat, prompt_template=VALUES_CLARIFICATION_PROMPT)


def _explain_agent() -> ExplainAgent:
    return ExplainAgent()


def _commerce_agent(*, deps: AppDeps, alignment: AlignmentService) -> CommerceAgent:
    def search(q, client_id, brand_id):
        return _search_products(
            deps=deps, query=q, client_id=client_id, brand_id=brand_id
        )

    return CommerceAgent(
        builder=CommercePlanBuilder(
            search_fn=search,
            compare_fn=compare_products,
            build_profile_fn=build_profile,
        ),
        reason_fn=reason_about_products_default,
        assess_fn=alignment.assess,
        score_fn=alignment.score_products,
        search_fn=search,
    )


def _service(*, deps: AppDeps) -> ConversationService:
    return ConversationService(deps=deps)


class ClarifiedGoal(BaseModel):
    goal_text: str = Field(..., description="Goal description in the user's own words.")
    domain: Optional[str] = None
    importance: Optional[float] = Field(default=0.7, ge=0.0, le=1.0)


class ConversationStartRequest(BaseModel):
    user_id: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)
    brand_id: Optional[str] = Field(default=None)
    opening_message: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    clarified_goals: Optional[List[ClarifiedGoal]] = None


class MessageRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    clarified_goals: Optional[List[ClarifiedGoal]] = None


class ClarifiedGoalsRequest(BaseModel):
    goals: List[ClarifiedGoal]
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None


class ResearchRequest(BaseModel):
    user_id: Optional[str] = None
    query: Optional[str] = None
    client_id: Optional[str] = None


def _sse_event(data: Dict[str, Any], event: str | None = None) -> str:
    payload = json.dumps(data)
    if event:
        return f"event: {event}\ndata: {payload}\n\n"
    return f"data: {payload}\n\n"


def _chunk_text(text: str, size: int = 24) -> List[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


@router.post("/start")
def start_conversation(request: ConversationStartRequest) -> Dict[str, Any]:
    deps = _deps()
    alignment = _alignment(deps)
    service = _service(deps=deps)
    goal_agent = GOAL_AGENT or _goal_agent()
    intent_agent = INTENT_AGENT or _intent_agent()
    commerce_agent = COMMERCE_AGENT or _commerce_agent(deps=deps, alignment=alignment)
    explain_agent = EXPLAIN_AGENT or _explain_agent()
    client_id = require_client_id(request.client_id, request.user_id)
    return service.start(
        user_id=request.user_id,
        client_id=client_id,
        brand_id=request.brand_id,
        opening_message=request.opening_message,
        metadata=request.metadata,
        clarified_goals=request.clarified_goals,
        goal_agent=goal_agent,
        intent_agent=intent_agent,
        commerce_agent=commerce_agent,
        explain_agent=explain_agent,
        run_research_fn=run_research,
        score_alignment_fn=alignment.score_products,
        build_profile_with_llm_fn=lambda product: _build_profile_with_llm(
            product, deps=deps
        ),
    )


@router.post("/start/stream")
def start_conversation_stream(
    request: ConversationStartRequest,
) -> StreamingResponse:
    deps = _deps()
    alignment = _alignment(deps)
    service = _service(deps=deps)
    goal_agent = GOAL_AGENT or _goal_agent()
    intent_agent = INTENT_AGENT or _intent_agent()
    commerce_agent = COMMERCE_AGENT or _commerce_agent(deps=deps, alignment=alignment)
    explain_agent = EXPLAIN_AGENT or _explain_agent()
    client_id = require_client_id(request.client_id, request.user_id)

    def event_stream():
        yield _sse_event({"phase": "processing"}, event="status")
        payload = service.start(
            user_id=request.user_id,
            client_id=client_id,
            brand_id=request.brand_id,
            opening_message=request.opening_message,
            metadata=request.metadata,
            clarified_goals=request.clarified_goals,
            goal_agent=goal_agent,
            intent_agent=intent_agent,
            commerce_agent=commerce_agent,
            explain_agent=explain_agent,
            run_research_fn=run_research,
            score_alignment_fn=alignment.score_products,
            build_profile_with_llm_fn=lambda product: _build_profile_with_llm(
                product, deps=deps
            ),
        )
        explanation = payload.get("explanation") or ""
        for chunk in _chunk_text(str(explanation)):
            yield _sse_event({"content": chunk}, event="delta")
        yield _sse_event({"phase": "finalizing"}, event="status")
        yield _sse_event(payload, event="conversation")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/message")
def continue_conversation(session_id: str, request: MessageRequest) -> Dict[str, Any]:
    deps = _deps()
    alignment = _alignment(deps)
    service = _service(deps=deps)
    goal_agent = GOAL_AGENT or _goal_agent()
    intent_agent = INTENT_AGENT or _intent_agent()
    commerce_agent = COMMERCE_AGENT or _commerce_agent(deps=deps, alignment=alignment)
    explain_agent = EXPLAIN_AGENT or _explain_agent()
    client_id = require_client_id(request.client_id, request.user_id)
    return service.continue_message(
        session_id=session_id,
        user_id=request.user_id,
        client_id=client_id,
        brand_id=request.brand_id,
        message=request.message,
        metadata=request.metadata,
        clarified_goals=request.clarified_goals,
        goal_agent=goal_agent,
        intent_agent=intent_agent,
        commerce_agent=commerce_agent,
        explain_agent=explain_agent,
        run_research_fn=run_research,
        score_alignment_fn=alignment.score_products,
        build_profile_with_llm_fn=lambda product: _build_profile_with_llm(
            product, deps=deps
        ),
    )


@router.post("/{session_id}/stream")
def continue_conversation_stream(
    session_id: str, request: MessageRequest
) -> StreamingResponse:
    deps = _deps()
    alignment = _alignment(deps)
    service = _service(deps=deps)
    goal_agent = GOAL_AGENT or _goal_agent()
    intent_agent = INTENT_AGENT or _intent_agent()
    commerce_agent = COMMERCE_AGENT or _commerce_agent(deps=deps, alignment=alignment)
    explain_agent = EXPLAIN_AGENT or _explain_agent()
    client_id = require_client_id(request.client_id, request.user_id)

    def event_stream():
        yield _sse_event({"phase": "processing"}, event="status")
        payload = service.continue_message(
            session_id=session_id,
            user_id=request.user_id,
            client_id=client_id,
            brand_id=request.brand_id,
            message=request.message,
            metadata=request.metadata,
            clarified_goals=request.clarified_goals,
            goal_agent=goal_agent,
            intent_agent=intent_agent,
            commerce_agent=commerce_agent,
            explain_agent=explain_agent,
            run_research_fn=run_research,
            score_alignment_fn=alignment.score_products,
            build_profile_with_llm_fn=lambda product: _build_profile_with_llm(
                product, deps=deps
            ),
        )
        explanation = payload.get("explanation") or ""
        for chunk in _chunk_text(str(explanation)):
            yield _sse_event({"content": chunk}, event="delta")
        yield _sse_event({"phase": "finalizing"}, event="status")
        yield _sse_event(payload, event="conversation")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions")
def list_sessions(
    user_id: Optional[str] = None,
    limit: int = 20,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    deps = _deps()
    service = _service(deps=deps)
    client_scope = require_client_id(client_id, user_id)
    return service.list_sessions(user_id=user_id, limit=limit, client_id=client_scope)


@router.get("/{session_id}")
def get_session_snapshot(
    session_id: str, user_id: Optional[str] = None, client_id: Optional[str] = None
) -> Dict[str, Any]:
    deps = _deps()
    service = _service(deps=deps)
    client_scope = require_client_id(client_id, user_id)
    return service.get_snapshot(
        session_id=session_id, user_id=user_id, client_id=client_scope
    )


@router.delete("/{session_id}")
def delete_session(
    session_id: str, user_id: Optional[str] = None, client_id: Optional[str] = None
) -> Dict[str, str]:
    deps = _deps()
    service = _service(deps=deps)
    client_scope = require_client_id(client_id, user_id)
    return service.delete_session(
        session_id=session_id, user_id=user_id, client_id=client_scope
    )


@router.post("/{session_id}/goals")
def ingest_clarified_goals(
    session_id: str, request: ClarifiedGoalsRequest
) -> Dict[str, Any]:
    deps = _deps()
    service = _service(deps=deps)
    client_id = require_client_id(request.client_id, request.user_id)
    return service.ingest_goals(
        session_id=session_id,
        user_id=request.user_id,
        client_id=client_id,
        brand_id=request.brand_id,
        goals=request.goals,
    )


@router.post("/{session_id}/research")
def refresh_research(session_id: str, request: ResearchRequest) -> Dict[str, Any]:
    deps = _deps()
    alignment = _alignment(deps)
    service = _service(deps=deps)
    client_id = require_client_id(request.client_id, request.user_id)
    return service.refresh_research(
        session_id=session_id,
        user_id=request.user_id,
        client_id=client_id,
        query=request.query,
        run_research_fn=run_research,
        score_alignment_fn=alignment.score_products,
    )
