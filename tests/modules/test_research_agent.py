from __future__ import annotations

from shared.db.connection import init_db, set_database_path
from infrastructure.memory.semantic_memory import SemanticMemory
from infrastructure.llm.research_agent import run_research
from shared.config.env import settings


def test_research_agent_executes_tool_calls(monkeypatch, tmp_path):
    db_path = tmp_path / "research.db"
    set_database_path(db_path)
    init_db()

    def fake_generate_with_tools(prompt, tools, system_instruction=None, provider=None):
        return {
            "tool_calls": [
                {
                    "name": "memory_write",
                    "args": {
                        "key": "goals",
                        "value": "Find supportive running shoes",
                        "mode": "append",
                    },
                }
            ],
            "text": "Stub research summary",
        }

    monkeypatch.setattr(
        "infrastructure.llm.research_agent.generate_with_tools",
        fake_generate_with_tools,
    )
    monkeypatch.setattr(settings, "llm_provider", "openai")

    result = run_research(
        "running shoes", goals=["Reduce pain"], context="Session context"
    )
    assert result["tool_calls"]

    memory = SemanticMemory()
    assert "Find supportive running shoes" in memory.get("goals")
