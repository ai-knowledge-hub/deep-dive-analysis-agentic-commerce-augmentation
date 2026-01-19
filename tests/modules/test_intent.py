from modules.intent.classifier import classify


def test_workspace_intent_detected():
    result = classify("Need a desk setup refresh with ergonomic chair suggestions")
    assert result.primary_goal == "workspace upgrade"
    assert result.domain == "career"
    assert "desk" in result.context_signals


def test_unknown_intent_when_no_keywords():
    result = classify("Tell me a story about nothing in particular")
    assert result.primary_goal == "unknown"
    assert result.confidence < 0.3


def test_llm_fallback_parses_multi_goal_payload():
    def llm_stub(text: str):
        return {
            "primary_goal": "design focused workspace",
            "secondary_goals": ["reduce distractions", "improve posture"],
            "underlying_needs": ["comfort", "focus"],
            "context_signals": ["ergonomic", "quiet"],
            "confidence": 0.82,
            "domain": "career",
            "source": "llm",
        }

    result = classify("Need a focus setup", llm_fallback=llm_stub, llm_threshold=0.1)
    assert result.primary_goal == "design focused workspace"
    assert result.secondary_goals == ["reduce distractions", "improve posture"]
    assert result.underlying_needs == ["comfort", "focus"]
    assert result.context_signals == ["ergonomic", "quiet"]
    assert result.domain == "career"
