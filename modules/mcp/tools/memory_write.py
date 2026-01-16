"""Tool for writing to semantic memory with consent-aware metadata."""

from __future__ import annotations

from typing import List

from modules.memory.semantic import SemanticMemory


def run(
    key: str,
    values: List[str] | None = None,
    value: str | None = None,
    mode: str = "append",
) -> dict:
    """Write memory entries (append/set) to semantic memory."""
    memory = SemanticMemory()
    current = memory.get(key)

    if mode not in {"append", "set"}:
        return {"error": "mode must be 'append' or 'set'."}

    if mode == "set":
        new_values = list(values or ([] if value is None else [value]))
        memory.set(key, new_values)
        return {"key": key, "values": new_values, "mode": mode}

    if value is None:
        return {"error": "value is required when mode='append'."}
    memory.append(key, value)
    return {"key": key, "values": current + [value], "mode": mode}


__all__ = ["run"]
