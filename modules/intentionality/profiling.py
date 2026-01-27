"""Compatibility shim for intentionality profiling.

Canonical implementation lives in `application.services.intentionality_profiler`.
"""

from __future__ import annotations

from typing import Callable

from application.services.intentionality_profiler import (
    IntentionalityProfile,
    build_profile as _build_profile,
    build_profile_with_llm as _build_profile_with_llm,
)


def build_profile(product, generate_fn: Callable[[str], str] | None = None) -> IntentionalityProfile:
    return _build_profile(product, generate_fn=generate_fn)


def build_profile_with_llm(product) -> IntentionalityProfile:
    return _build_profile_with_llm(product)


__all__ = ["build_profile", "build_profile_with_llm"]
