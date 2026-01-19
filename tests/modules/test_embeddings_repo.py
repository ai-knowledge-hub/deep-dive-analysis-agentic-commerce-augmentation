from pathlib import Path

from shared.db.connection import init_db, set_database_path
from modules.intent.embeddings import get_intent_embedding, upsert_intent_embedding
from modules.commerce.embeddings import get_product_embedding, upsert_product_embedding


def test_intent_embedding_round_trip(tmp_path: Path):
    db_path = tmp_path / "embeddings.db"
    set_database_path(db_path)
    init_db()

    embedding = [0.1, 0.2, 0.3]
    upsert_intent_embedding("reduce back pain", embedding, payload={"domain": "health"})

    stored = get_intent_embedding("reduce back pain")
    assert stored is not None
    assert stored["embedding"] == embedding
    assert stored["payload"]["domain"] == "health"


def test_product_embedding_round_trip(tmp_path: Path):
    db_path = tmp_path / "embeddings.db"
    set_database_path(db_path)
    init_db()

    embedding = [0.4, 0.5, 0.6]
    upsert_product_embedding("product-1", embedding, payload={"source": "mock"})

    stored = get_product_embedding("product-1")
    assert stored is not None
    assert stored["embedding"] == embedding
