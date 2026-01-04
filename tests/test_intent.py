from src.intent.classifier import classify


def test_workspace_intent_detected():
    result = classify("Need a desk setup refresh with ergonomic chair suggestions")
    assert result.label == "workspace_upgrade"
    assert result.domain == "career"
    assert "desk" in result.evidence


def test_unknown_intent_when_no_keywords():
    result = classify("Tell me a story about nothing in particular")
    assert result.label == "unknown"
    assert result.confidence < 0.3
