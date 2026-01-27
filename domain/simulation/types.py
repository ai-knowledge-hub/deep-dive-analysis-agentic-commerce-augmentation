"""Pure types for simulation sandbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SimulationProduct:
    """Minimal product representation for simulation runs."""

    id: str
    name: str
    description: str
    source: str = "simulation"
    url: Optional[str] = None
    price: Optional[float] = None
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationRun:
    """Persisted simulation run."""

    id: str
    user_id: Optional[str]
    session_id: Optional[str]
    query: str
    scenario: Dict[str, Any]
    products: List[Dict[str, Any]]
    result: Dict[str, Any]
    retest: Optional[Dict[str, Any]] = None


__all__ = ["SimulationProduct", "SimulationRun"]
