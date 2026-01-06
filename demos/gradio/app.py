"""Hackathon-friendly Gradio surface that calls the façade agents."""

from __future__ import annotations

try:
    import gradio as gr
except ImportError:  # pragma: no cover - optional dependency
    gr = None

from dataclasses import asdict
from datetime import datetime
import uuid

from agents.intent_agent import IntentAgent
from agents.commerce_agent import CommerceAgent
from agents.reflection_agent import ReflectionAgent
from agents.autonomy_guard_agent import AutonomyGuardAgent
from agents.explain_agent import ExplainAgent
from attribution.events import get_default_recorder
from attribution.models import IntentEvent, RecommendationEvent
from src.memory.session_manager import SessionManager
from llm.agents.product_reasoner import reason_about_products


def _run_agentic_flow(message: str, user_id: str | None = None, platform: str = "gradio") -> dict:
    user_id = user_id or str(uuid.uuid4())
    session_manager = SessionManager(user_id=user_id)
    intent_agent = IntentAgent()
    commerce_agent = CommerceAgent()
    reflection_agent = ReflectionAgent()
    autonomy_guard = AutonomyGuardAgent()
    explain_agent = ExplainAgent()
    recorder = get_default_recorder()

    session_manager.record_turn("user", message, metadata={"platform": platform})

    intent = intent_agent.detect_intent(message)
    session_manager.ingest_intent_as_goal(intent)
    recorder.record_intent(
        IntentEvent(
            user_id=user_id,
            platform=platform,
            intent_label=intent["label"],
            metadata={"confidence": str(intent.get("confidence", 0.0))},
            created_at=datetime.utcnow(),
        )
    )

    goals = session_manager.goal_texts()
    plan = commerce_agent.build_plan(intent, goals=goals)
    plan["products"] = reason_about_products(goals, plan.get("products", []))
    recorder.record_recommendation(
        RecommendationEvent(
            user_id=user_id,
            platform=platform,
            product_ids=[product["id"] for product in plan.get("products", [])],
            empowering_score=plan["data_quality"].get("average_confidence", 0.0),
            memory_snapshot={"plan_query": intent.get("label", "")},
            created_at=datetime.utcnow(),
        )
    )

    clarifications = plan.get("clarifications", [])
    guard_result = autonomy_guard.check(
        rationale="; ".join(clarifications), clarifications=clarifications, products=plan.get("products", [])
    )
    reflection = reflection_agent.reflect(plan)
    explanation = explain_agent.explain(plan.get("products", []))
    session_manager.record_turn(
        "agent",
        " | ".join(clarifications) or "Plan shared.",
        metadata={"type": "clarifications"},
    )
    session_manager.record_recommendation(
        product_ids=[product["id"] for product in plan.get("products", [])],
        empowering_score=(plan.get("empowerment", {}).get("goal_alignment", {}) or {}).get("score"),
        context={
            "query": plan.get("query"),
            "goal_alignment": plan.get("empowerment", {}).get("goal_alignment"),
            "data_quality": plan.get("data_quality"),
        },
    )
    session_manager.record_reflection(reflection)
    session_manager.update_state(
        last_query=plan.get("query"),
        last_intent=intent,
        last_empowerment=plan.get("empowerment"),
    )
    session_snapshot = asdict(session_manager.summary())
    reasoning_text = _summarize_reasoning(plan.get("products", []))

    return {
        "intent": intent,
        "plan": plan,
        "explanation": explanation,
        "reflection": reflection,
        "guardrails": guard_result,
        "user_id": user_id,
        "session": session_snapshot,
        "reasoning": reasoning_text,
    }


def _gradio_flow(message: str) -> tuple[dict, str, str, str, dict, str]:
    payload = _run_agentic_flow(message)
    plan = payload["plan"]
    clarifications = "\n".join(plan.get("clarifications", [])) or "No clarifications."
    return (
        plan,
        clarifications,
        payload["explanation"],
        payload["reflection"],
        payload["guardrails"],
        payload["reasoning"],
    )


def _summarize_reasoning(products: list[dict]) -> str:
    if not products:
        return "No products available."
    lines = []
    for product in products:
        reasoning = product.get("reasoning", "No reasoning provided.")
        lines.append(f"**{product.get('name')}**\n{reasoning}")
    return "\n\n".join(lines)


def build_interface() -> "gr.Blocks":  # type: ignore[name-defined]
    if gr is None:
        raise RuntimeError("gradio is not installed")
    with gr.Blocks() as demo:
        gr.Markdown("## Agentic Commerce Demo")
        input_box = gr.Textbox(label="User Request", placeholder="Describe your goal...")
        plan_json = gr.JSON(label="Plan (with data-quality metrics)")
        clarifications_box = gr.Textbox(label="Clarifications", lines=3)
        explanation_box = gr.Textbox(label="Explanation")
        reflection_box = gr.Textbox(label="Reflection")
        guard_box = gr.JSON(label="Autonomy Guard Result")
        reasoning_box = gr.Markdown(label="Product Reasoning")
        input_box.submit(
            _gradio_flow,
            inputs=input_box,
            outputs=[plan_json, clarifications_box, explanation_box, reflection_box, guard_box, reasoning_box],
        )
    return demo


if __name__ == "__main__" and gr is not None:
    build_interface().launch()
