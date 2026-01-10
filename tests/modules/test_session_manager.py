from pathlib import Path

from modules.memory.session_manager import SessionManager


def test_session_manager_tracks_goals_and_turns(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    manager = SessionManager(user_id="test-user", db_path=db_path)
    manager.record_turn("user", "Need a better chair")
    manager.record_goal("Reduce back pain", domain="health", importance=0.9)
    manager.record_turn("agent", "Logged your goal.", metadata={"type": "ack"})
    manager.record_recommendation(["p1", "p2"], empowering_score=0.8)
    manager.record_reflection("Session captured.")

    goals = manager.goal_texts()
    assert "Reduce back pain" in goals

    snapshot = manager.summary()
    assert snapshot.session["id"]
    assert len(snapshot.turns) == 2
    assert snapshot.latest_episode is not None
