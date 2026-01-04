import json
from pathlib import Path

from src.memory.semantic import SemanticMemory
from src.memory.working import WorkingMemory


def test_semantic_memory_loads_from_json(tmp_path: Path):
    data_path = tmp_path / "memory.json"
    payload = {"goals": ["Rest more"], "capabilities": ["Stretching"], "episodes": []}
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    memory = SemanticMemory(data_path=data_path)
    assert memory.get("goals") == ["Rest more"]
    memory.append("goals", "Build stamina")
    updated = json.loads(data_path.read_text())
    assert "Build stamina" in updated["goals"]


def test_working_memory_tracks_turns():
    memory = WorkingMemory()
    memory.add("user", "Need better focus")
    memory.add("agent", "Recommending ergo setup")
    transcript = memory.summarize()
    assert "user: Need better focus" in transcript
    assert len(memory.last()) == 2
