import pytest

try:
    import gradio as gr  # noqa: F401
except ImportError:
    gr = None

from demos.gradio.app import _run_agentic_flow


def test_run_agentic_flow_returns_expected_keys(monkeypatch):
    if gr is None:
        pytest.skip("gradio not installed")

    mock_response = {
        "intent": {"label": "workspace"},
        "plan": {
            "products": [{"id": "p1", "confidence": 0.6, "source": "google_shopping"}],
            "clarifications": ["Mock clarification"],
        },
        "explanation": "Mock explanation",
        "reflection": "Mock reflection",
        "guardrails": {"status": "clear"},
    }

    monkeypatch.setattr("demos.gradio.app._run_agentic_flow", lambda message: mock_response)

    result = _run_agentic_flow("Need a new desk")
    assert set(result.keys()) == {"intent", "plan", "explanation", "reflection", "guardrails", "user_id"}
