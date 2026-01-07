"""Maps semantic memory into capability statements."""

from __future__ import annotations

from src.memory.semantic import SemanticMemory


class CapabilityAgent:
    def summarize(self) -> dict:
        memory = SemanticMemory()
        return {
            "goals": memory.get("goals"),
            "capabilities": memory.get("capabilities"),
        }
