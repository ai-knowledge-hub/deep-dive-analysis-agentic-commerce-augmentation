from pathlib import Path

from dataclasses import replace

from infrastructure.memory.semantic_memory import SemanticMemory
from application.services.conversation.session_manager import SessionManager
import infrastructure.db.session.goals as goals_repo
from domain.memory.working import WorkingMemory
from api.composition import default_deps


def test_semantic_memory_persists_in_sqlite(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    memory = SemanticMemory(data_path=db_path)
    memory.set("goals", ["Rest more"])
    memory.append("goals", "Build stamina")

    new_instance = SemanticMemory(data_path=db_path)
    assert "Rest more" in new_instance.get("goals")
    assert "Build stamina" in new_instance.get("goals")


def test_working_memory_tracks_turns():
    memory = WorkingMemory()
    memory.add("user", "Need better focus")
    memory.add("agent", "Recommending ergo setup")
    transcript = memory.summarize()
    assert "user: Need better focus" in transcript
    assert len(memory.last()) == 2


def test_goal_embedding_persists_in_goals_table(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "goals.db"
    deps = replace(
        default_deps(),
        embedding_available=lambda: True,
        embed=lambda text: [0.11, 0.22, 0.33],
    )
    manager = SessionManager(deps=deps, db_path=db_path)
    goal = manager.record_goal("Reduce back pain")

    stored = goals_repo.list_goals_for_session(
        session_id=manager.session_id, client_id=manager.client_id
    )
    assert stored
    assert stored[0]["goal_text"] == goal["goal_text"]
    assert stored[0]["goal_embedding"] == [0.11, 0.22, 0.33]
