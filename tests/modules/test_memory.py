from pathlib import Path

from modules.memory.semantic import SemanticMemory
from modules.memory.working import WorkingMemory


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
