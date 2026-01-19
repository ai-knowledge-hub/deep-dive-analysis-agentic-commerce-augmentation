"""Conversation endpoints exposing session + discovery telemetry."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modules.conversation.agents import (
    IntentAgent,
    CommerceAgent,
    ExplainAgent,
)
from modules.memory.session_manager import SessionManager
from modules.values.agent import ValuesAgent
from modules.values.domain import ClarificationState
from modules.conversation.context import context_for
from modules.conversation.research import run_research
from modules.alignment.goal_alignment import score_products as score_alignment
from modules.intentionality.profiling import build_profile_with_llm
from modules.intentionality.domain import IntentionalityProfile
from modules.commerce.domain import Product

router = APIRouter(prefix="/conversation", tags=["conversation"])

INTENT_AGENT = IntentAgent()
COMMERCE_AGENT = CommerceAgent()
EXPLAIN_AGENT = ExplainAgent()
VALUES_AGENT = ValuesAgent()


class ClarifiedGoal(BaseModel):
    goal_text: str = Field(..., description="Goal description in the user's own words.")
    domain: Optional[str] = None
    importance: Optional[float] = Field(default=0.7, ge=0.0, le=1.0)


class ConversationStartRequest(BaseModel):
    user_id: Optional[str] = Field(default=None)
    opening_message: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    clarified_goals: Optional[List[ClarifiedGoal]] = None


class MessageRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    clarified_goals: Optional[List[ClarifiedGoal]] = None


class ClarifiedGoalsRequest(BaseModel):
    goals: List[ClarifiedGoal]
    user_id: Optional[str] = None


def _session_response(manager: SessionManager, **payload: Any) -> Dict[str, Any]:
    snapshot = asdict(manager.summary())
    response: Dict[str, Any] = {
        "session_id": manager.session_id,
        "user_id": manager.user_id,
        "snapshot": snapshot,
    }
    response.update(payload)
    return response


def _process_message(
    manager: SessionManager,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    clarified_goals: Optional[List[ClarifiedGoal]] = None,
) -> Dict[str, Any]:
    if clarified_goals:
        for clarified_goal in clarified_goals:
            manager.record_goal(
                clarified_goal.goal_text,
                domain=clarified_goal.domain,
                importance=clarified_goal.importance or 0.7,
            )

    manager.record_turn("user", message, metadata=metadata or {})

    clarification_state, clarification_reply = _handle_values_dialogue(
        manager, message, metadata
    )
    if clarification_reply:
        return _session_response(
            manager,
            clarification=clarification_reply,
            values_state=clarification_state.to_dict() if clarification_state else None,
        )

    _, context_snapshot = context_for(manager)

    intent = INTENT_AGENT.detect_intent(message, manager=manager)
    manager.ingest_intent_as_goal(intent)
    goals = manager.goal_texts()
    intent_signal = intent.get("primary_goal") or intent.get("label") or ""
    if intent_signal:
        manager.record_turn(
            "agent",
            f"Intent inferred: {intent_signal}",
            metadata={
                "type": "intent_inference",
                "confidence": intent.get("confidence"),
            },
        )
    plan = COMMERCE_AGENT.build_plan(intent, goals=goals, context=context_snapshot)
    goal_signals = _goal_signals(intent, goals)
    product_explanations = plan.get("product_explanations")
    if not product_explanations:
        product_explanations = _format_reasoning(plan.get("products", []))
    clarifications = plan.get("clarifications", [])
    explanation = EXPLAIN_AGENT.explain(plan.get("products", []))
    manager.record_turn(
        "agent",
        explanation,
        metadata={"type": "plan_explanation", "clarifications": clarifications},
    )
    manager.record_recommendation(
        product_ids=[product["id"] for product in plan.get("products", [])],
        alignment_score=(plan.get("alignment", {}).get("goal_alignment", {}) or {}).get(
            "score"
        ),
        context={
            "query": plan.get("query"),
            "goal_alignment": plan.get("alignment", {}).get("goal_alignment"),
            "data_quality": plan.get("data_quality"),
        },
    )
    manager.update_state(
        last_intent=intent,
        last_query=plan.get("query"),
        last_alignment=plan.get("alignment"),
    )

    research = _maybe_run_research(plan, goals, context_snapshot)
    research_stream = _build_research_stream(research, goal_signals)

    return _session_response(
        manager,
        intent=intent,
        plan=_merge_plan_streams(plan, research_stream),
        research=research,
        baseline_alignment=plan.get("alignment", {})
        .get("goal_alignment", {})
        .get("baseline_score")
        or 0.0,
        intentionality_profiles=_intentionality_profiles(plan.get("products") or []),
        explanation=explanation,
        product_explanations=product_explanations,
        values_state=clarification_state.to_dict()
        if clarification_state
        else manager.get_state().get("clarification_state"),
    )


def _handle_values_dialogue(
    manager: SessionManager,
    message: str,
    metadata: Optional[Dict[str, Any]],
) -> tuple[Optional[ClarificationState], Optional[str]]:
    state_payload = manager.get_state().get("clarification_state")
    state = ClarificationState.from_dict(state_payload) if state_payload else None
    if state and state.ready_for_products:
        return state, None

    if state:
        state = VALUES_AGENT.continue_dialogue(state, message)
    else:
        state = VALUES_AGENT.start(message, metadata or {})

    manager.update_state(clarification_state=state.to_dict())
    latest_turn = state.turns[-1] if state.turns else None
    if not state.ready_for_products and latest_turn and latest_turn.speaker == "agent":
        manager.record_turn(
            "agent", latest_turn.content, metadata={"type": "clarification"}
        )
        return state, latest_turn.content

    if state.ready_for_products:
        for goal in state.extracted_goals:
            try:
                manager.record_goal(goal)
            except ValueError:
                continue
    return state, None


def _format_reasoning(products: List[dict]) -> List[dict]:
    explanations: List[dict] = []
    for product in products or []:
        explanations.append(
            {
                "id": product.get("id"),
                "name": product.get("name"),
                "reasoning": product.get("reasoning", ""),
                "capabilities_enabled": product.get("capabilities_enabled", []),
                "confidence": product.get("confidence"),
            }
        )
    return explanations


def _intentionality_profiles(products: List[object]) -> List[dict]:
    profiles: List[dict] = []
    for product in products or []:
        if isinstance(product, Product):
            profiles.append(build_profile_with_llm(product).to_dict())
            continue
        if isinstance(product, dict):
            profile = product.get("intentionality_profile")
            if profile:
                profiles.append(profile)
                continue
            capabilities = list(product.get("capabilities_enabled") or [])
            profile = IntentionalityProfile(
                product_id=str(product.get("id") or ""),
                capabilities_enabled=capabilities,
                goals_served=list(dict.fromkeys(capabilities)),
                prerequisites=[],
                outcomes_expected=[],
                context_fit={},
            )
            profiles.append(profile.to_dict())
            continue
    return profiles


def _maybe_run_research(
    plan: dict, goals: List[str], context_snapshot: str | None
) -> dict | None:
    query = plan.get("query") or "catalog research"
    return run_research(query=query, goals=goals, context=context_snapshot)


def _goal_signals(intent: dict, goals: List[str]) -> List[str]:
    merged: List[str] = []
    if goals:
        merged.extend(goals)
    primary = intent.get("primary_goal") or intent.get("label")
    if primary and primary != "unknown":
        merged.append(primary)
    merged.extend(intent.get("secondary_goals") or [])
    merged.extend(intent.get("underlying_needs") or [])
    seen = set()
    deduped = []
    for goal in merged:
        if goal and goal != "unknown" and goal not in seen:
            seen.add(goal)
            deduped.append(goal)
    return deduped


def _build_research_stream(research: dict | None, goals: List[str]) -> dict | None:
    if not research:
        return None
    insights = research.get("insights", []) or []
    if not insights:
        return {"items": [], "alignment": {"per_item": []}}

    items = []
    for insight in insights:
        title = insight.get("title") or insight.get("summary") or "Research insight"
        summary = insight.get("summary") or title
        items.append(
            {
                "id": insight.get("id") or title,
                "name": title,
                "price": 0.0,
                "description": summary,
                "confidence": insight.get("confidence", 0.35),
                "source": "research",
                "capabilities_enabled": [],
                "tags": ["research"],
            }
        )

    products = [Product(**item) for item in items]
    scores = score_alignment(goals, products) if goals else []
    per_item = {score.product_id: score.__dict__ for score in scores}
    enriched = []
    for item in items:
        score = per_item.get(item["id"], {})
        enriched.append(
            {
                **item,
                "alignment_score": score.get("score"),
                "alignment_reasoning": score.get("alignment_reasoning"),
            }
        )
    return {"items": enriched, "alignment": {"per_item": list(per_item.values())}}


def _merge_plan_streams(plan: dict, research_stream: dict | None) -> dict:
    merged = dict(plan)
    merged["catalog_results"] = plan.get("products", [])
    merged["research_results"] = research_stream.get("items") if research_stream else []
    merged["alignment"] = merged.get("alignment") or {}
    merged["alignment"]["research"] = (
        research_stream.get("alignment") if research_stream else {}
    )
    return merged


@router.post("/start")
def start_conversation(request: ConversationStartRequest) -> Dict[str, Any]:
    manager = SessionManager(user_id=request.user_id)
    if request.opening_message:
        return _process_message(
            manager,
            request.opening_message,
            request.metadata,
            clarified_goals=request.clarified_goals,
        )
    if request.clarified_goals:
        for clarified_goal in request.clarified_goals:
            manager.record_goal(
                clarified_goal.goal_text,
                domain=clarified_goal.domain,
                importance=clarified_goal.importance or 0.7,
            )
    return _session_response(manager)


@router.post("/{session_id}/message")
def continue_conversation(session_id: str, request: MessageRequest) -> Dict[str, Any]:
    manager = SessionManager(session_id=session_id, user_id=request.user_id)
    if not request.message:
        raise HTTPException(status_code=400, detail="message is required")
    return _process_message(
        manager,
        request.message,
        request.metadata,
        clarified_goals=request.clarified_goals,
    )


@router.get("/{session_id}")
def get_session_snapshot(
    session_id: str, user_id: Optional[str] = None
) -> Dict[str, Any]:
    manager = SessionManager(session_id=session_id, user_id=user_id)
    return _session_response(manager)


@router.post("/{session_id}/goals")
def ingest_clarified_goals(
    session_id: str, request: ClarifiedGoalsRequest
) -> Dict[str, Any]:
    if not request.goals:
        raise HTTPException(status_code=400, detail="At least one goal is required.")

    manager = SessionManager(session_id=session_id, user_id=request.user_id)
    for clarified_goal in request.goals:
        manager.record_goal(
            clarified_goal.goal_text,
            domain=clarified_goal.domain,
            importance=clarified_goal.importance or 0.7,
        )

    return _session_response(manager, goals=manager.goal_texts())
