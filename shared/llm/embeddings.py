"""Hybrid embedding generation with Gemini + local fallback.

Provides semantic similarity capabilities for goal-product alignment.
Uses Gemini text-embedding-004 as primary, sentence-transformers as fallback.
"""

from __future__ import annotations

import hashlib
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------


@dataclass
class EmbeddingConfig:
    """Configuration for embedding providers."""

    # Gemini settings
    gemini_model: str = "text-embedding-004"
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    gemini_task_type: str = "SEMANTIC_SIMILARITY"

    # Local model settings
    local_model: str = "all-MiniLM-L6-v2"

    # Cache settings
    cache_size: int = 1000

    # Behavior
    prefer_local: bool = field(
        default_factory=lambda: os.getenv("EMBEDDING_PREFER_LOCAL", "false").lower()
        == "true"
    )


# -----------------------------------------------------------------------------
# Abstract Base
# -----------------------------------------------------------------------------


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name."""
        ...


# -----------------------------------------------------------------------------
# Gemini Provider
# -----------------------------------------------------------------------------


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Gemini text-embedding-004 provider (free tier available)."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._client = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        if not self.config.gemini_api_key:
            raise ValueError("Gemini API key not configured")

        from google import genai

        self._client = genai.Client(api_key=self.config.gemini_api_key)
        self._initialized = True
        logger.info("Gemini embedding provider initialized")

    def embed(self, text: str) -> List[float]:
        self._ensure_initialized()

        response = self._client.models.embed_content(
            model=self.config.gemini_model,
            contents=text,
            config={"task_type": self.config.gemini_task_type},
        )
        return list(response.embeddings[0].values)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self._ensure_initialized()

        # Gemini supports batch embedding
        response = self._client.models.embed_content(
            model=self.config.gemini_model,
            contents=texts,
            config={"task_type": self.config.gemini_task_type},
        )
        return [list(emb.values) for emb in response.embeddings]

    @property
    def dimension(self) -> int:
        return 768  # text-embedding-004 dimension

    @property
    def name(self) -> str:
        return "gemini"


# -----------------------------------------------------------------------------
# Local Provider (Sentence Transformers)
# -----------------------------------------------------------------------------


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers provider (no API needed)."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._model = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.config.local_model)
            self._initialized = True
            logger.info(
                f"Local embedding provider initialized with {self.config.local_model}"
            )
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )

    def embed(self, text: str) -> List[float]:
        self._ensure_initialized()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self._ensure_initialized()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        return 384  # all-MiniLM-L6-v2 dimension

    @property
    def name(self) -> str:
        return "local"


# -----------------------------------------------------------------------------
# Hybrid Provider with Caching
# -----------------------------------------------------------------------------


class HybridEmbeddingProvider:
    """Hybrid provider with Gemini primary + local fallback and caching."""

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self._gemini: Optional[GeminiEmbeddingProvider] = None
        self._local: Optional[LocalEmbeddingProvider] = None
        self._cache: Dict[
            str, Tuple[List[float], str]
        ] = {}  # hash -> (embedding, provider)
        self._active_provider: Optional[EmbeddingProvider] = None

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()

    def _get_gemini(self) -> GeminiEmbeddingProvider:
        if self._gemini is None:
            self._gemini = GeminiEmbeddingProvider(self.config)
        return self._gemini

    def _get_local(self) -> LocalEmbeddingProvider:
        if self._local is None:
            self._local = LocalEmbeddingProvider(self.config)
        return self._local

    def _select_provider(self) -> EmbeddingProvider:
        """Select best available provider."""
        if self._active_provider:
            return self._active_provider

        # Prefer local if configured
        if self.config.prefer_local:
            try:
                provider = self._get_local()
                provider._ensure_initialized()
                self._active_provider = provider
                return provider
            except Exception as e:
                logger.warning(f"Local provider failed: {e}, trying Gemini")

        # Try Gemini first (better quality)
        if self.config.gemini_api_key:
            try:
                provider = self._get_gemini()
                provider._ensure_initialized()
                self._active_provider = provider
                return provider
            except Exception as e:
                logger.warning(f"Gemini provider failed: {e}, falling back to local")

        # Fallback to local
        try:
            provider = self._get_local()
            provider._ensure_initialized()
            self._active_provider = provider
            return provider
        except Exception as e:
            raise RuntimeError(f"No embedding provider available: {e}")

    def embed(self, text: str) -> List[float]:
        """Generate embedding with caching."""
        cache_key = self._get_cache_key(text)

        if cache_key in self._cache:
            return self._cache[cache_key][0]

        provider = self._select_provider()
        embedding = provider.embed(text)

        # Cache with size limit
        if len(self._cache) >= self.config.cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[cache_key] = (embedding, provider.name)
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch, using cache where possible."""
        results: List[Optional[List[float]]] = [None] * len(texts)
        texts_to_embed: List[Tuple[int, str]] = []

        # Check cache first
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                results[i] = self._cache[cache_key][0]
            else:
                texts_to_embed.append((i, text))

        # Embed uncached texts
        if texts_to_embed:
            provider = self._select_provider()
            uncached_texts = [text for _, text in texts_to_embed]
            new_embeddings = provider.embed_batch(uncached_texts)

            for (orig_idx, text), embedding in zip(texts_to_embed, new_embeddings):
                results[orig_idx] = embedding
                cache_key = self._get_cache_key(text)

                if len(self._cache) >= self.config.cache_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

                self._cache[cache_key] = (embedding, provider.name)

        return results  # type: ignore

    @property
    def dimension(self) -> int:
        """Return dimension of active provider."""
        return self._select_provider().dimension

    @property
    def provider_name(self) -> str:
        """Return name of active provider."""
        return self._select_provider().name

    def clear_cache(self) -> None:
        """Clear embedding cache."""
        self._cache.clear()


# -----------------------------------------------------------------------------
# Similarity Functions
# -----------------------------------------------------------------------------


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)

    dot_product = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


def batch_cosine_similarity(
    query_embedding: List[float], candidate_embeddings: List[List[float]]
) -> List[float]:
    """Compute cosine similarity between query and multiple candidates."""
    query = np.array(query_embedding)
    candidates = np.array(candidate_embeddings)

    # Normalize
    query_norm = query / (np.linalg.norm(query) + 1e-10)
    candidate_norms = candidates / (
        np.linalg.norm(candidates, axis=1, keepdims=True) + 1e-10
    )

    # Dot product
    similarities = np.dot(candidate_norms, query_norm)
    return similarities.tolist()


# -----------------------------------------------------------------------------
# Singleton Access
# -----------------------------------------------------------------------------

_provider_singleton: Optional[HybridEmbeddingProvider] = None


def get_embedding_provider() -> HybridEmbeddingProvider:
    """Get the singleton embedding provider."""
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = HybridEmbeddingProvider()
    return _provider_singleton


def embed(text: str) -> List[float]:
    """Generate embedding for text using default provider."""
    return get_embedding_provider().embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for texts using default provider."""
    return get_embedding_provider().embed_batch(texts)


def similarity(text_a: str, text_b: str) -> float:
    """Compute semantic similarity between two texts."""
    provider = get_embedding_provider()
    emb_a = provider.embed(text_a)
    emb_b = provider.embed(text_b)
    return cosine_similarity(emb_a, emb_b)


__all__ = [
    "EmbeddingConfig",
    "EmbeddingProvider",
    "GeminiEmbeddingProvider",
    "LocalEmbeddingProvider",
    "HybridEmbeddingProvider",
    "cosine_similarity",
    "batch_cosine_similarity",
    "get_embedding_provider",
    "embed",
    "embed_batch",
    "similarity",
]
