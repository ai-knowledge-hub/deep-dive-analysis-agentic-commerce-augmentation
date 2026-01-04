"""Shared product schemas for the agentic commerce core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Product:
    id: str
    name: str
    price: float
    tags: List[str]
