"""High-level helper to orchestrate sessions, turns, and goal ingestion.

This is the canonical SessionManager used by application services and API routes.
Legacy import paths under `modules.memory.session_manager` re-export this class.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from domain.memory.types import SessionSnapshot
from infrastructure.db.connection import init_db, set_database_path
from infrastructure.db import episodes as episodes_store
from infrastructure.db import goals as goals_store
from infrastructure.db import recommendations as recommendations_store
from infrastructure.db import sessions as sessions_store
from infrastructure.db import turns as turns_store
from infrastructure.db import users as users_store
from infrastructure.llm.gateway import embed, embedding_available
from infrastructure.memory.semantic_memory import SemanticMemory
from infrastructure.db import semantic as semantic_store


def _normalize_goal_text(goal: str | None) -> str | None:
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
        client_id: str | None = None,
        brand_id: str | None = None,
    ) -> None:
        if db_path:
            set_database_path(db_path)
        init_db()

        self.user_id = user_id or semantic_store.DEFAULT_USER_ID
        self.client_id = client_id or semantic_store.DEFAULT_CLIENT_ID
        self.brand_id = brand_id
        users_store.ensure_user(self.user_id)

        self._session = self._resolve_session(session_id=session_id, state=state or {})
        self.session_id = self._session["id"]
        self._state = self._session.get("state") or {}
        self._memory = SemanticMemory(user_id=self.user_id, client_id=self.client_id)

    def _resolve_session(
        self, session_id: str | None, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        if session_id:
            existing = sessions_store.get_session(
                session_id=session_id, client_id=self.client_id
            )
            if existing:
                return existing
        return sessions_store.create_session(
            user_id=self.user_id,
            state=state,
            client_id=self.client_id,
            brand_id=self.brand_id,
        )

    # ------------------------------------------------------------------ turns
    def record_turn(
        self, speaker: str, content: str, metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        return turns_store.add_turn(
            session_id=self.session_id,
            speaker=speaker,
            content=content,
            metadata=metadata or {},
        )

    def list_turns(self, limit: int = 100) -> List[Dict[str, Any]]:
        return turns_store.list_turns(session_id=self.session_id, limit=limit)

    # ------------------------------------------------------------------ goals
    def record_goal(
        self,
        goal_text: str,
        domain: str | None = None,
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        normalized_goal = _normalize_goal_text(goal_text)
        if not normalized_goal:
            raise ValueError("Goal text cannot be empty.")
        goal_embedding: list[float] | None = None
        if embedding_available():
            try:
                goal_embedding = embed(normalized_goal)
            except Exception:
                goal_embedding = None
        entry = goals_store.create_goal(
            user_id=self.user_id,
            goal_text=normalized_goal,
            session_id=self.session_id,
            domain=domain,
            importance=importance,
            goal_embedding=goal_embedding,
            client_id=self.client_id,
            brand_id=self.brand_id,
        )
        existing_goals = self._memory.get("goals")
        if normalized_goal not in existing_goals:
            self._memory.append("goals", normalized_goal)
        return entry

    def ingest_intent_as_goal(self, intent: Dict[str, Any]) -> None:
        goal = intent.get("primary_goal") or intent.get("label")
        if not goal or goal == "unknown":
            return
        domain = intent.get("domain")
        importance = float(intent.get("confidence", 0.5) or 0.5)
        self.record_goal(goal, domain=domain, importance=importance)

    def goal_texts(self) -> List[str]:
        session_goals = [
            goal["goal_text"]
            for goal in goals_store.list_goals_for_session(
                session_id=self.session_id, client_id=self.client_id
            )
        ]
        semantic_goals = self._memory.get("goals")
        seen: list[str] = []
        for goal in session_goals + semantic_goals:
            if goal not in seen:
                seen.append(goal)
        return seen

    # ---------------------------------------------------------------- recommendations
    def record_recommendation(
        self,
        product_ids: List[str],
        alignment_score: float | None,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return recommendations_store.create_recommendation(
            session_id=self.session_id,
            product_ids=product_ids,
            alignment_score=alignment_score,
            context=context or {},
            client_id=self.client_id,
        )

    # ---------------------------------------------------------------- episodic memory
    def record_outcome(
        self, outcome_text: str, outcome: str | None = "outcome_summary"
    ) -> Dict[str, Any]:
        return episodes_store.create_episode(
            user_id=self.user_id,
            session_id=self.session_id,
            outcome=outcome,
            takeaways=[outcome_text],
            client_id=self.client_id,
        )

    # ---------------------------------------------------------------- state helpers
    def update_state(self, **updates: Any) -> None:
        self._state.update(updates)
        sessions_store.update_state(session_id=self.session_id, state=self._state)

    def get_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def summary(self, include_turn_limit: int = 50) -> SessionSnapshot:
        return SessionSnapshot(
            session=self._session_info(),
            turns=self.list_turns(limit=include_turn_limit),
            goals=[
                goal["goal_text"]
                for goal in goals_store.list_goals_for_session(
                    session_id=self.session_id, client_id=self.client_id
                )
            ],
            semantic_goals=self._memory.get("goals"),
            latest_episode=episodes_store.get_latest(
                user_id=self.user_id, client_id=self.client_id
            ),
        )

    def _session_info(self) -> Dict[str, Any]:
        refreshed = (
            sessions_store.get_session(
                session_id=self.session_id, client_id=self.client_id
            )
            or self._session
        )
        state = refreshed.get("state") or {}
        return {
            "id": refreshed["id"],
            "user_id": refreshed["user_id"],
            "client_id": refreshed["client_id"],
            "brand_id": refreshed["brand_id"],
            "created_at": refreshed["created_at"],
            "state": state,
        }


__all__ = ["SessionManager", "SessionSnapshot"]
