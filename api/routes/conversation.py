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

router = APIRouter(prefix="/conversation", tags=["conversation"])

DEPS = default_deps()
ALIGNMENT = AlignmentService(DEPS)


def build_profile_with_llm(product: Any) -> Any:
    return build_profile(product, generate_fn=DEPS.generate)


INTENT_AGENT = IntentAgent(
    classifier=build_intent_classifier(),
    context_for_fn=context_for,
    log_replay_fn=log_intent_replay,
)


def _search_products(query: str, client_id: str | None, brand_id: str | None):
    if not client_id:
        return []
    return search_products_for_client(
        deps=DEPS, query=query, client_id=client_id, brand_id=brand_id
    )


COMMERCE_AGENT = CommerceAgent(
    builder=CommercePlanBuilder(
        search_fn=_search_products,
        compare_fn=compare_products,
        build_profile_fn=build_profile,
    ),
    reason_fn=reason_about_products_default,
    assess_fn=ALIGNMENT.assess,
    score_fn=ALIGNMENT.score_products,
    search_fn=_search_products,
)
EXPLAIN_AGENT = ExplainAgent()
GOAL_AGENT = GoalClarificationAgent(
    chat_fn=chat, prompt_template=VALUES_CLARIFICATION_PROMPT
)
SERVICE = ConversationService(deps=DEPS)


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
    client_id = require_client_id(request.client_id, request.user_id)
    return SERVICE.start(
        user_id=request.user_id,
        client_id=client_id,
        brand_id=request.brand_id,
        opening_message=request.opening_message,
        metadata=request.metadata,
        clarified_goals=request.clarified_goals,
        goal_agent=GOAL_AGENT,
        intent_agent=INTENT_AGENT,
        commerce_agent=COMMERCE_AGENT,
        explain_agent=EXPLAIN_AGENT,
        run_research_fn=run_research,
        score_alignment_fn=ALIGNMENT.score_products,
        build_profile_with_llm_fn=build_profile_with_llm,
    )


@router.post("/start/stream")
def start_conversation_stream(
    request: ConversationStartRequest,
) -> StreamingResponse:
    client_id = require_client_id(request.client_id, request.user_id)

    def event_stream():
        yield _sse_event({"phase": "processing"}, event="status")
        payload = SERVICE.start(
            user_id=request.user_id,
            client_id=client_id,
            brand_id=request.brand_id,
            opening_message=request.opening_message,
            metadata=request.metadata,
            clarified_goals=request.clarified_goals,
            goal_agent=GOAL_AGENT,
            intent_agent=INTENT_AGENT,
            commerce_agent=COMMERCE_AGENT,
            explain_agent=EXPLAIN_AGENT,
            run_research_fn=run_research,
            score_alignment_fn=ALIGNMENT.score_products,
            build_profile_with_llm_fn=build_profile_with_llm,
        )
        explanation = payload.get("explanation") or ""
        for chunk in _chunk_text(str(explanation)):
            yield _sse_event({"content": chunk}, event="delta")
        yield _sse_event({"phase": "finalizing"}, event="status")
        yield _sse_event(payload, event="conversation")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/message")
def continue_conversation(session_id: str, request: MessageRequest) -> Dict[str, Any]:
    client_id = require_client_id(request.client_id, request.user_id)
    return SERVICE.continue_message(
        session_id=session_id,
        user_id=request.user_id,
        client_id=client_id,
        brand_id=request.brand_id,
        message=request.message,
        metadata=request.metadata,
        clarified_goals=request.clarified_goals,
        goal_agent=GOAL_AGENT,
        intent_agent=INTENT_AGENT,
        commerce_agent=COMMERCE_AGENT,
        explain_agent=EXPLAIN_AGENT,
        run_research_fn=run_research,
        score_alignment_fn=ALIGNMENT.score_products,
        build_profile_with_llm_fn=build_profile_with_llm,
    )


@router.post("/{session_id}/stream")
def continue_conversation_stream(
    session_id: str, request: MessageRequest
) -> StreamingResponse:
    client_id = require_client_id(request.client_id, request.user_id)

    def event_stream():
        yield _sse_event({"phase": "processing"}, event="status")
        payload = SERVICE.continue_message(
            session_id=session_id,
            user_id=request.user_id,
            client_id=client_id,
            brand_id=request.brand_id,
            message=request.message,
            metadata=request.metadata,
            clarified_goals=request.clarified_goals,
            goal_agent=GOAL_AGENT,
            intent_agent=INTENT_AGENT,
            commerce_agent=COMMERCE_AGENT,
            explain_agent=EXPLAIN_AGENT,
            run_research_fn=run_research,
            score_alignment_fn=ALIGNMENT.score_products,
            build_profile_with_llm_fn=build_profile_with_llm,
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
    client_scope = require_client_id(client_id, user_id)
    return SERVICE.list_sessions(user_id=user_id, limit=limit, client_id=client_scope)


@router.get("/{session_id}")
def get_session_snapshot(
    session_id: str, user_id: Optional[str] = None, client_id: Optional[str] = None
) -> Dict[str, Any]:
    client_scope = require_client_id(client_id, user_id)
    return SERVICE.get_snapshot(
        session_id=session_id, user_id=user_id, client_id=client_scope
    )


@router.delete("/{session_id}")
def delete_session(
    session_id: str, user_id: Optional[str] = None, client_id: Optional[str] = None
) -> Dict[str, str]:
    client_scope = require_client_id(client_id, user_id)
    return SERVICE.delete_session(
        session_id=session_id, user_id=user_id, client_id=client_scope
    )


@router.post("/{session_id}/goals")
def ingest_clarified_goals(
    session_id: str, request: ClarifiedGoalsRequest
) -> Dict[str, Any]:
    client_id = require_client_id(request.client_id, request.user_id)
    return SERVICE.ingest_goals(
        session_id=session_id,
        user_id=request.user_id,
        client_id=client_id,
        brand_id=request.brand_id,
        goals=request.goals,
    )


@router.post("/{session_id}/research")
def refresh_research(session_id: str, request: ResearchRequest) -> Dict[str, Any]:
    client_id = require_client_id(request.client_id, request.user_id)
    return SERVICE.refresh_research(
        session_id=session_id,
        user_id=request.user_id,
        client_id=client_id,
        query=request.query,
        run_research_fn=run_research,
        score_alignment_fn=ALIGNMENT.score_products,
    )
