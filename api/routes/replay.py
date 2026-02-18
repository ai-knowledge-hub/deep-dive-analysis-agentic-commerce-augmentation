from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, HTTPException
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore
    HTTPException = None  # type: ignore

from api.utils.tenancy import is_admin, require_client_id
import infrastructure.db.session.replays as replays_repo

if APIRouter:
    router = APIRouter(prefix="/replay", tags=["replay"])

    @router.get("/records")
    def list_records(
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        run_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        client_scope = require_client_id(client_id, user_id)
        if not is_admin(user_id) and not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        records = replays_repo.list_replay_records(
            client_id=client_scope,
            user_id=None if is_admin(user_id) else user_id,
            session_id=session_id,
            entity_type=entity_type,
            entity_id=entity_id,
            run_type=run_type,
            limit=limit,
        )
        return {"records": records}

    @router.get("/records/{replay_id}")
    def get_record(
        replay_id: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        client_scope = require_client_id(client_id, user_id)
        record = replays_repo.get_replay_record(
            replay_id,
            client_id=client_scope,
            user_id=None if is_admin(user_id) else user_id,
        )
        if not record:
            raise HTTPException(status_code=404, detail="Replay not found")
        return {"record": record}

else:
    router = None
