"""Backward compatibility: re-exports from modules.memory.repositories.recommendations."""

from modules.memory.repositories.recommendations import (
    create_recommendation,
    list_recommendations,
)

__all__ = ["create_recommendation", "list_recommendations"]
