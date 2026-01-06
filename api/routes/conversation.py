"""Conversation endpoints exposing session + empowerment telemetry."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.intent_agent import IntentAgent
from agents.commerce_agent import CommerceAgent
from agents.reflection_agent import ReflectionAgent
from agents.autonomy_guard_agent import AutonomyGuardAgent
from agents.explain_agent import ExplainAgent
from src.memory.session_manager import SessionManager
from llm.agents.values import ValuesAgent, ClarificationState
from llm.agents.product_reasoner import reason_about_products

router = APIRouter(prefix="/conversation", tags=["conversation"])

INTENT_AGENT = IntentAgent()
COMMERCE_AGENT = CommerceAgent()
REFLECTION_AGENT = ReflectionAgent()
AUTONOMY_GUARD = AutonomyGuardAgent()
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

    clarification_state, clarification_reply = _handle_values_dialogue(manager, message, metadata)
    if clarification_reply:
        return _session_response(
            manager,
            clarification=clarification_reply,
            values_state=clarification_state.to_dict() if clarification_state else None,
        )

    intent = INTENT_AGENT.detect_intent(message)
    manager.ingest_intent_as_goal(intent)
    goals = manager.goal_texts()
    plan = COMMERCE_AGENT.build_plan(intent, goals=goals)
    plan["products"] = reason_about_products(goals, plan.get("products", []))
    product_explanations = _format_reasoning(plan.get("products", []))
    clarifications = plan.get("clarifications", [])
    guard = AUTONOMY_GUARD.check(
        rationale="; ".join(clarifications),
        clarifications=clarifications,
        products=plan.get("products", []),
    )
    explanation = EXPLAIN_AGENT.explain(plan.get("products", []))
    reflection = REFLECTION_AGENT.reflect(plan)

    manager.record_turn(
        "agent",
        explanation,
        metadata={"type": "plan_explanation", "clarifications": clarifications},
    )
    manager.record_recommendation(
        product_ids=[product["id"] for product in plan.get("products", [])],
        empowering_score=(
            plan.get("empowerment", {}).get("goal_alignment", {}) or {}
        ).get("score"),
        context={
            "query": plan.get("query"),
            "goal_alignment": plan.get("empowerment", {}).get("goal_alignment"),
            "data_quality": plan.get("data_quality"),
        },
    )
    manager.record_reflection(reflection)
    manager.update_state(
        last_intent=intent,
        last_query=plan.get("query"),
        last_empowerment=plan.get("empowerment"),
    )

    return _session_response(
        manager,
        intent=intent,
        plan=plan,
        guardrails=guard,
        explanation=explanation,
        reflection=reflection,
        product_explanations=product_explanations,
        values_state=clarification_state.to_dict() if clarification_state else manager.get_state().get("clarification_state"),
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
        manager.record_turn("agent", latest_turn.content, metadata={"type": "clarification"})
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
def get_session_snapshot(session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    manager = SessionManager(session_id=session_id, user_id=user_id)
    return _session_response(manager)


@router.post("/{session_id}/goals")
def ingest_clarified_goals(session_id: str, request: ClarifiedGoalsRequest) -> Dict[str, Any]:
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
