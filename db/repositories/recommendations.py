"""Backward compatibility: re-exports from infrastructure DB recommendations."""

from infrastructure.db.recommendations import (
    create_recommendation,
    list_recommendations,
)

__all__ = ["create_recommendation", "list_recommendations"]
