"""Intent embedding storage helpers."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json
from shared.llm.embeddings import embed


def _serialize_embedding(embedding: List[float] | None) -> bytes | None:
    if embedding is None:
        return None
    return json.dumps(embedding).encode("utf-8")


def _deserialize_embedding(raw: bytes | None) -> List[float] | None:
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def upsert_intent_embedding(
    intent_text: str,
    embedding: List[float] | None,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Upsert an intent embedding by intent text."""
    intent_id = str(uuid.uuid5(uuid.NAMESPACE_URL, intent_text))
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO intent_embeddings (id, intent_text, embedding, payload_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            embedding=excluded.embedding,
            payload_json=excluded.payload_json,
            created_at=datetime('now')
        """,
        (
            intent_id,
            intent_text,
            _serialize_embedding(embedding),
            to_json(payload),
        ),
    )
    conn.commit()
    return {
        "id": intent_id,
        "intent_text": intent_text,
        "embedding": embedding,
        "payload": payload,
    }


def get_intent_embedding(intent_text: str) -> Dict[str, Any] | None:
    """Fetch an intent embedding by intent text."""
    intent_id = str(uuid.uuid5(uuid.NAMESPACE_URL, intent_text))
    row = (
        get_connection()
        .execute("SELECT * FROM intent_embeddings WHERE id = ?", (intent_id,))
        .fetchone()
    )
    if not row:
        return None
    return {
        "id": row["id"],
        "intent_text": row["intent_text"],
        "embedding": _deserialize_embedding(row["embedding"]),
        "payload": from_json(row["payload_json"], default={}),
    }


def embed_and_store_intent(
    intent_text: str, payload: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Generate an embedding and store it for the intent text."""
    embedding = embed(intent_text)
    return upsert_intent_embedding(intent_text, embedding, payload=payload)


__all__ = [
    "upsert_intent_embedding",
    "get_intent_embedding",
    "embed_and_store_intent",
]
