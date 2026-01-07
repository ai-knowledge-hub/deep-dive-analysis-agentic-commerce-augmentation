from __future__ import annotations

from typing import List
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Provide lightweight google.genai stubs so importing the Gemini client
# (which happens when llm modules are imported) does not require the SDK.
if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(generate_content=lambda **_: types.SimpleNamespace(text=""))

    class GenerateContentConfig:
        def __init__(self, temperature: float = 0.7, max_output_tokens: int = 2048):
            self.temperature = temperature
            self.max_output_tokens = max_output_tokens
            self.tools = None

    class FunctionDeclaration:
        def __init__(self, name: str, description: str | None = None, parameters: dict | None = None):
            self.name = name
            self.description = description
            self.parameters = parameters

    class Tool:
        def __init__(self, function_declarations: list[FunctionDeclaration] | None = None):
            self.function_declarations = function_declarations or []

    genai_pkg.Client = DummyClient
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    genai_types_pkg.GenerateContentConfig = GenerateContentConfig
    genai_types_pkg.FunctionDeclaration = FunctionDeclaration
    genai_types_pkg.Tool = Tool

    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from llm.agents.intent_classifier import HybridIntentClassifier
from llm.agents.values import ClarificationState, ValuesAgent
from llm.agents.product_reasoner import reason_about_products
from src.intent.classifier import Intent as KeywordIntent


def test_hybrid_intent_prefers_llm_response(monkeypatch):
    def fake_generate(prompt: str, system_instruction: str | None = None, provider: str | None = None) -> str:
        return (
            '{"intent": "workspace_upgrade", "confidence": 0.9, '
            '"evidence": ["desk"], "clarifying_questions": ["q1"], "domain": "career"}'
        )

    monkeypatch.setattr("llm.agents.intent_classifier.generate", fake_generate)
    classifier = HybridIntentClassifier()

    result = classifier.classify("Need a better desk setup")

    assert result.label == "workspace_upgrade"
    assert result.source == "gemini"
    assert result.confidence == pytest.approx(0.9)
    assert "desk" in result.evidence


def test_hybrid_intent_falls_back_to_keywords(monkeypatch):
    def fake_generate(prompt: str, system_instruction: str | None = None, provider: str | None = None) -> str:
        return '{"intent": "unknown", "confidence": 0.2, "evidence": [], "clarifying_questions": []}'

    fallback_intent = KeywordIntent(
        label="workspace_upgrade",
        confidence=0.85,
        evidence=["workspace"],
        domain="career",
        clarifying_questions=["What triggers this need?"],
    )

    monkeypatch.setattr("llm.agents.intent_classifier.generate", fake_generate)
    monkeypatch.setattr(
        "llm.agents.intent_classifier.keyword_classifier.classify",
        lambda _: fallback_intent,
    )

    classifier = HybridIntentClassifier()
    result = classifier.classify("Need help")

    assert result.label == "workspace_upgrade"
    assert result.source == "keyword_fallback"
    assert result.confidence == pytest.approx(0.85)
    assert "workspace" in result.evidence


def test_values_agent_start_records_turns(monkeypatch):
    def fake_chat(messages: List[dict]) -> str:
        assert messages[0]["content"].startswith("You are")
        return "Let's explore what matters most to you."

    monkeypatch.setattr("llm.agents.values.chat", fake_chat)

    agent = ValuesAgent()
    state = agent.start("Help me design a calmer workspace", metadata={"channel": "test"})

    assert len(state.turns) == 2
    assert state.turns[0].content == "Help me design a calmer workspace"
    assert "matters most" in state.turns[1].content
    assert state.metadata == {"channel": "test"}
    assert not state.ready_for_products


def test_values_agent_continue_marks_ready(monkeypatch):
    summary_response = """Here's what I'm hearing:
    - Goal: reduce stress in your home office
    - Goal: enable longer focus blocks

    Does that capture it?"""

    def fake_chat(messages: List[dict]) -> str:
        # respond with summary to trigger ready_for_products
        return summary_response

    monkeypatch.setattr("llm.agents.values.chat", fake_chat)

    state = ClarificationState(query="Need focus")
    state.add_turn("user", "Need focus")
    state.add_turn("agent", "Tell me more.")

    agent = ValuesAgent()
    updated = agent.continue_dialogue(state, "Long calls drain me")

    assert updated.ready_for_products is True
    assert any("reduce stress" in goal.lower() for goal in updated.extracted_goals)
    assert updated.turns[-1].speaker == "agent"
    assert "Does that capture" in updated.turns[-1].content


def test_product_reasoner_attaches_reasoning(monkeypatch):
    prompts: list[str] = []

    def fake_generate(prompt: str, system_instruction: str | None = None, provider: str | None = None) -> str:
        prompts.append(prompt)
        return "Supports posture goals and keeps you focused."

    monkeypatch.setattr("llm.agents.product_reasoner.generate", fake_generate)

    products = [
        {
            "id": "p1",
            "name": "Focus Chair",
            "capabilities_enabled": ["Posture support"],
            "confidence": 0.72,
            "source": "mock",
        }
    ]

    result = reason_about_products(["Reduce back pain"], products)

    assert len(result) == 1
    assert result[0]["reasoning"] == "Supports posture goals and keeps you focused."
    assert "Reduce back pain" in prompts[0]
    assert "Focus Chair" in prompts[0]


def test_product_reasoner_handles_empty_products(monkeypatch):
    called = {"count": 0}

    def fake_generate(prompt: str, system_instruction: str | None = None, provider: str | None = None) -> str:
        called["count"] += 1
        return ""

    monkeypatch.setattr("llm.agents.product_reasoner.generate", fake_generate)

    assert reason_about_products(["Improve focus"], []) == []
    assert called["count"] == 0
