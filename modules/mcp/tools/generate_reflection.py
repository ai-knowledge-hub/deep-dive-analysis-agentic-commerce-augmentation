"""MCP tool that emits empowerment-aware reflections."""

from __future__ import annotations

from typing import List

from modules.empowerment import reflection


def run(entries: List[str]) -> dict:
    """Generate a reflection string from conversation highlights."""
    return {"reflection": reflection.generate(entries)}


__all__ = ["run"]
