from __future__ import annotations

from typing import List

from shared.llm.embeddings import (
    batch_cosine_similarity as _batch_cosine_similarity,
    embed_batch as _embed_batch,
    embedding_available as _embedding_available,
)


def embedding_available() -> bool:
    return _embedding_available()


def embed_batch(texts: List[str]) -> List[List[float]]:
    return _embed_batch(texts)


def batch_cosine_similarity(vec: List[float], vecs: List[List[float]]) -> List[float]:
    return _batch_cosine_similarity(vec, vecs)


__all__ = ["embedding_available", "embed_batch", "batch_cosine_similarity"]
