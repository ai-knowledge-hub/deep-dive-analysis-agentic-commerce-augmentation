from __future__ import annotations

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
            self.models = types.SimpleNamespace(
                generate_content=lambda **_: types.SimpleNamespace(text="")
            )

    class GenerateContentConfig:
        def __init__(self, temperature: float = 0.7, max_output_tokens: int = 2048):
            self.temperature = temperature
            self.max_output_tokens = max_output_tokens
            self.tools = None

    class FunctionDeclaration:
        def __init__(
            self,
            name: str,
            description: str | None = None,
            parameters: dict | None = None,
        ):
            self.name = name
            self.description = description
            self.parameters = parameters

    class Tool:
        def __init__(
            self, function_declarations: list[FunctionDeclaration] | None = None
        ):
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

from application.services.conversation.goal_clarification_service import (
    GoalClarificationService,
)
from domain.values.types import GoalClarificationState
from domain.intent.types import InferredIntent as KeywordIntent
from infrastructure.llm.hybrid_intent_classifier import HybridIntentClassifier
from infrastructure.llm.product_reasoner import reason_about_products
from infrastructure.llm.prompts import VALUES_CLARIFICATION_PROMPT


def test_hybrid_intent_prefers_llm_response(monkeypatch):
    def fake_generate(
        prompt: str, system_instruction: str | None = None, provider: str | None = None
    ) -> str:
        return (
            '{"primary_goal": "workspace upgrade", "confidence": 0.9, '
            '"context_signals": ["desk"], "underlying_needs": ["comfort"], "domain": "career"}'
        )

    fallback_intent = KeywordIntent(
        primary_goal="unknown",
        secondary_goals=[],
        underlying_needs=[],
        context_signals=[],
        confidence=0.1,
        domain="unknown",
        source="keyword",
    )

    def fake_keyword(
        text: str, llm_fallback=None, llm_threshold: float = 0.55, **kwargs
    ):
        if not llm_fallback:
            return fallback_intent
        llm_data = dict(llm_fallback(text) or {})
        if float(llm_data.get("confidence") or 0.0) >= llm_threshold:
            return KeywordIntent(
                primary_goal=str(llm_data.get("primary_goal") or "unknown"),
                secondary_goals=list(llm_data.get("secondary_goals") or []),
                underlying_needs=list(llm_data.get("underlying_needs") or []),
                context_signals=list(llm_data.get("context_signals") or []),
                confidence=float(llm_data.get("confidence") or 0.0),
                domain=str(llm_data.get("domain") or "") or None,
                source=str(llm_data.get("source") or "gemini"),
            )
        return fallback_intent

    classifier = HybridIntentClassifier(
        generate_fn=fake_generate,
        keyword_classify_fn=fake_keyword,
        prompt_template="{}",
    )

    result = classifier.classify("Need a better desk setup")

    assert result.primary_goal == "workspace upgrade"
    assert result.source == "gemini"
    assert result.confidence == pytest.approx(0.9)
    assert "desk" in result.context_signals


def test_hybrid_intent_falls_back_to_keywords(monkeypatch):
    def fake_generate(
        prompt: str, system_instruction: str | None = None, provider: str | None = None
    ) -> str:
        return '{"primary_goal": "unknown", "confidence": 0.2, "context_signals": []}'

    fallback_intent = KeywordIntent(
        primary_goal="workspace upgrade",
        secondary_goals=[],
        underlying_needs=["What triggers this need?"],
        context_signals=["workspace"],
        confidence=0.85,
        domain="career",
        source="keyword_fallback",
    )

    def fake_keyword(text: str, **kwargs):
        return fallback_intent

    classifier = HybridIntentClassifier(
        generate_fn=fake_generate,
        keyword_classify_fn=fake_keyword,
        prompt_template="{}",
    )
    result = classifier.classify("Need help")

    assert result.primary_goal == "workspace upgrade"
    assert result.source == "keyword_fallback"
    assert result.confidence == pytest.approx(0.85)
    assert "workspace" in result.context_signals


def test_values_agent_start_records_turns(monkeypatch):
    def fake_chat(messages: list[dict], system_instruction: str | None = None) -> str:
        assert system_instruction and system_instruction.startswith("You are")
        return "Let's explore what matters most to you."

    service = GoalClarificationService(
        chat_fn=fake_chat, prompt_template=VALUES_CLARIFICATION_PROMPT
    )
    state = service.start(
        query="Help me design a calmer workspace", metadata={"channel": "test"}
    )

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

    def fake_chat(messages: list[dict], system_instruction: str | None = None) -> str:
        # respond with summary to trigger ready_for_products
        return summary_response

    state = GoalClarificationState(query="Need focus")
    state.add_turn("user", "Need focus")
    state.add_turn("agent", "Tell me more.")

    service = GoalClarificationService(
        chat_fn=fake_chat, prompt_template=VALUES_CLARIFICATION_PROMPT
    )
    updated = service.continue_dialogue(state=state, user_message="Long calls drain me")

    assert updated.ready_for_products is True
    assert any("reduce stress" in goal.lower() for goal in updated.extracted_goals)
    assert updated.turns[-1].speaker == "agent"
    assert "Does that capture" in updated.turns[-1].content


def test_product_reasoner_attaches_reasoning(monkeypatch):
    prompts: list[str] = []

    def fake_generate(
        prompt: str, system_instruction: str | None = None, provider: str | None = None
    ) -> str:
        prompts.append(prompt)
        return "Supports posture goals and keeps you focused."

    products = [
        {
            "id": "p1",
            "name": "Focus Chair",
            "capabilities_enabled": ["Posture support"],
            "confidence": 0.72,
            "source": "mock",
        }
    ]

    result = reason_about_products(
        ["Reduce back pain"],
        products,
        generate_fn=lambda prompt: fake_generate(prompt),
        prompt_template="{goals}\n{product}",
    )

    assert len(result) == 1
    assert result[0]["reasoning"] == "Supports posture goals and keeps you focused."
    assert "Reduce back pain" in prompts[0]
    assert "Focus Chair" in prompts[0]


def test_product_reasoner_handles_empty_products(monkeypatch):
    called = {"count": 0}

    def fake_generate(
        prompt: str, system_instruction: str | None = None, provider: str | None = None
    ) -> str:
        called["count"] += 1
        return ""

    assert (
        reason_about_products(
            ["Improve focus"],
            [],
            generate_fn=lambda prompt: fake_generate(prompt),
            prompt_template="{goals}\n{product}",
        )
        == []
    )
    assert called["count"] == 0
