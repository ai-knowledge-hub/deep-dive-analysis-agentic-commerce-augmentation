"""Hackathon-friendly Gradio surface that calls the façade agents."""

from __future__ import annotations

try:
    import gradio as gr
except ImportError:  # pragma: no cover - optional dependency
    gr = None

from agents.intent_agent import IntentAgent
from agents.commerce_agent import CommerceAgent
from agents.reflection_agent import ReflectionAgent


def _run_agentic_flow(message: str) -> str:
    intent_agent = IntentAgent()
    commerce_agent = CommerceAgent()
    reflection_agent = ReflectionAgent()
    intent = intent_agent.detect_intent(message)
    plan = commerce_agent.build_plan(intent)
    reflection = reflection_agent.reflect(plan)
    return f"Intent: {intent}\nPlan: {plan}\nReflection: {reflection}"


def build_interface() -> "gr.Blocks":  # type: ignore[name-defined]
    if gr is None:
        raise RuntimeError("gradio is not installed")
    with gr.Blocks() as demo:
        gr.Markdown("## Agentic Commerce Demo")
        input_box = gr.Textbox(label="User Request", placeholder="Describe your goal...")
        output_box = gr.Textbox(label="Agent Output")
        input_box.submit(_run_agentic_flow, inputs=input_box, outputs=output_box)
    return demo


if __name__ == "__main__" and gr is not None:
    build_interface().launch()
