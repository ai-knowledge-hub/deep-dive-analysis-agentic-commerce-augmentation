"""Hackathon-friendly Gradio surface that calls the façade agents."""

from __future__ import annotations

try:
    import gradio as gr
except ImportError:  # pragma: no cover - optional dependency
    gr = None

from datetime import datetime
import uuid

from agents.intent_agent import IntentAgent
from agents.commerce_agent import CommerceAgent
from agents.reflection_agent import ReflectionAgent
from agents.autonomy_guard_agent import AutonomyGuardAgent
from agents.explain_agent import ExplainAgent
from attribution.events import get_default_recorder
from attribution.models import IntentEvent, RecommendationEvent


def _run_agentic_flow(message: str, user_id: str | None = None, platform: str = "gradio") -> dict:
    user_id = user_id or str(uuid.uuid4())
    intent_agent = IntentAgent()
    commerce_agent = CommerceAgent()
    reflection_agent = ReflectionAgent()
    autonomy_guard = AutonomyGuardAgent()
    explain_agent = ExplainAgent()
    recorder = get_default_recorder()

    intent = intent_agent.detect_intent(message)
    recorder.record_intent(
        IntentEvent(
            user_id=user_id,
            platform=platform,
            intent_label=intent["label"],
            metadata={"confidence": str(intent.get("confidence", 0.0))},
            created_at=datetime.utcnow(),
        )
    )

    plan = commerce_agent.build_plan(intent)
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

    return {
        "intent": intent,
        "plan": plan,
        "explanation": explanation,
        "reflection": reflection,
        "guardrails": guard_result,
        "user_id": user_id,
    }


def _gradio_flow(message: str) -> tuple[dict, str, str, str, dict]:
    payload = _run_agentic_flow(message)
    plan = payload["plan"]
    clarifications = "\n".join(plan.get("clarifications", [])) or "No clarifications."
    return plan, clarifications, payload["explanation"], payload["reflection"], payload["guardrails"]


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
        input_box.submit(_gradio_flow, inputs=input_box, outputs=[plan_json, clarifications_box, explanation_box, reflection_box, guard_box])
    return demo


if __name__ == "__main__" and gr is not None:
    build_interface().launch()
