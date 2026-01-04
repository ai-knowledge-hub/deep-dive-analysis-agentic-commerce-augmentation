"""MCP tool that emits empowerment-aware reflections."""

from __future__ import annotations

from typing import List

from src.empowerment import reflection


def run(entries: List[str]) -> dict:
    return {"reflection": reflection.generate(entries)}
