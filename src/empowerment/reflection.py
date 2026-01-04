"""Empowerment-aware reflection utilities."""

from __future__ import annotations

from typing import List


def generate(entries: List[str]) -> str:
    bullets = "\n".join(f"- {entry}" for entry in entries)
    return f"Reflection Points:\n{bullets}"
