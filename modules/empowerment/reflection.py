"""Empowerment-aware reflection utilities."""

from __future__ import annotations

from typing import List


def generate_reflection(entries: List[str]) -> str:
    """Generate reflection points from entries."""
    bullets = "\n".join(f"- {entry}" for entry in entries)
    return f"Reflection Points:\n{bullets}"


# Alias for backward compatibility
generate = generate_reflection

__all__ = ["generate_reflection", "generate"]
