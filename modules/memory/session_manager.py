"""High-level helper to orchestrate sessions, turns, and goal ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from shared.db.connection import init_db, set_database_path
from modules.memory.repositories import episodes as episodes_repo
from modules.memory.repositories import goals as goals_repo
from modules.memory.repositories import recommendations as recommendations_repo
from modules.memory.repositories import sessions as sessions_repo
from modules.memory.repositories import semantic as semantic_repo
from modules.memory.repositories import turns as turns_repo
from modules.memory.repositories import users as users_repo
from modules.memory.domain import SessionSnapshot
from modules.memory.semantic import SemanticMemory


def _normalize_goal_text(goal: str | None) -> str | None:
    """Normalize goal text by replacing underscores and trimming."""
    if not goal:
        return None
    return goal.replace("_", " ").strip()


class SessionManager:
    """Central coordinator tying SQLite repositories into the memory workflow."""

    def __init__(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        state: Dict[str, Any] | None = None,
        db_path: Path | None = None,
    ) -> None:
        if db_path:
            set_database_path(db_path)
        init_db()

        self.user_id = user_id or semantic_repo.DEFAULT_USER_ID
        users_repo.ensure_user(self.user_id)

        self._session = self._resolve_session(session_id=session_id, state=state or {})
        self.session_id = self._session["id"]
        self._state = self._session.get("state") or {}
        self._memory = SemanticMemory(user_id=self.user_id)

    def _resolve_session(self, session_id: str | None, state: Dict[str, Any]) -> Dict[str, Any]:
        """Find existing session or create new one."""
        if session_id:
            existing = sessions_repo.get_session(session_id)
            if existing:
                return existing
        return sessions_repo.create_session(user_id=self.user_id, state=state)

    # ------------------------------------------------------------------ turns
    def record_turn(
        self, speaker: str, content: str, metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Persist a conversational turn."""
        return turns_repo.add_turn(
            session_id=self.session_id,
            speaker=speaker,
            content=content,
            metadata=metadata or {},
        )

    def list_turns(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List turns for the current session."""
        return turns_repo.list_turns(self.session_id, limit=limit)

    # ------------------------------------------------------------------ goals
    def record_goal(
        self,
        goal_text: str,
        domain: str | None = None,
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        """Record a user goal."""
        normalized_goal = _normalize_goal_text(goal_text)
        if not normalized_goal:
            raise ValueError("Goal text cannot be empty.")
        entry = goals_repo.create_goal(
            user_id=self.user_id,
            goal_text=normalized_goal,
            session_id=self.session_id,
            domain=domain,
            importance=importance,
        )
        existing_goals = self._memory.get("goals")
        if normalized_goal not in existing_goals:
            self._memory.append("goals", normalized_goal)
        return entry

    def ingest_intent_as_goal(self, intent: Dict[str, Any]) -> None:
        """Treat detected intent as an initial goal signal."""
        goal = intent.get("label")
        if not goal or goal == "unknown":
            return
        domain = intent.get("domain")
        importance = float(intent.get("confidence", 0.5) or 0.5)
        self.record_goal(goal, domain=domain, importance=importance)

    def goal_texts(self) -> List[str]:
        """Get deduplicated list of goal texts from session and semantic memory."""
        session_goals = [goal["goal_text"] for goal in goals_repo.list_goals_for_session(self.session_id)]
        semantic_goals = self._memory.get("goals")
        seen = []
        for goal in session_goals + semantic_goals:
            if goal not in seen:
                seen.append(goal)
        return seen

    # ---------------------------------------------------------------- recommendations
    def record_recommendation(
        self,
        product_ids: List[str],
        empowering_score: float | None,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Record a product recommendation."""
        return recommendations_repo.create_recommendation(
            session_id=self.session_id,
            product_ids=product_ids,
            empowering_score=empowering_score,
            context=context or {},
        )

    # ---------------------------------------------------------------- episodic memory
    def record_reflection(
        self, reflection_text: str, outcome: str | None = "reflection_summary"
    ) -> Dict[str, Any]:
        """Record a reflection as an episode."""
        return episodes_repo.create_episode(
            user_id=self.user_id,
            session_id=self.session_id,
            outcome=outcome,
            takeaways=[reflection_text],
        )

    # ---------------------------------------------------------------- state helpers
    def update_state(self, **updates: Any) -> None:
        """Update session state."""
        self._state.update(updates)
        sessions_repo.update_state(self.session_id, self._state)

    def get_state(self) -> Dict[str, Any]:
        """Get current session state."""
        return dict(self._state)

    def summary(self, include_turn_limit: int = 50) -> SessionSnapshot:
        """Get a snapshot of the current session."""
        return SessionSnapshot(
            session=self._session_info(),
            turns=self.list_turns(limit=include_turn_limit),
            goals=[goal["goal_text"] for goal in goals_repo.list_goals_for_session(self.session_id)],
            semantic_goals=self._memory.get("goals"),
            latest_episode=episodes_repo.get_latest(self.user_id),
        )

    def _session_info(self) -> Dict[str, Any]:
        """Get session info dictionary."""
        refreshed = sessions_repo.get_session(self.session_id) or self._session
        state = refreshed.get("state") or {}
        return {
            "id": refreshed["id"],
            "user_id": refreshed["user_id"],
            "created_at": refreshed["created_at"],
            "state": state,
        }


__all__ = ["SessionManager", "SessionSnapshot"]
