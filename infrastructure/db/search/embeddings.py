"""SQLite repositories for intent/product embedding storage."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


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
        "payload": payload or {},
    }


def get_intent_embedding(intent_text: str) -> Dict[str, Any] | None:
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


def upsert_product_embedding(
    product_id: str, embedding: List[float] | None
) -> Dict[str, Any]:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO product_embeddings (product_id, embedding, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(product_id) DO UPDATE SET
            embedding=excluded.embedding,
            updated_at=datetime('now')
        """,
        (product_id, _serialize_embedding(embedding)),
    )
    conn.commit()
    return {"product_id": product_id, "embedding": embedding}


def get_product_embedding(product_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            "SELECT * FROM product_embeddings WHERE product_id = ?", (product_id,)
        )
        .fetchone()
    )
    if not row:
        return None
    return {"product_id": row["product_id"], "embedding": _deserialize_embedding(row["embedding"])}


__all__ = [
    "upsert_intent_embedding",
    "get_intent_embedding",
    "upsert_product_embedding",
    "get_product_embedding",
]

