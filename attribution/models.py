"""Dataclasses describing attribution events for AI-aware commerce."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class IntentEvent:
    user_id: str
    platform: str
    intent_label: str
    metadata: Dict[str, str]
    created_at: datetime


@dataclass
class RecommendationEvent:
    user_id: str
    platform: str
    product_ids: List[str]
    empowering_score: float
    memory_snapshot: Dict[str, str]
    created_at: datetime


@dataclass
class ConversionEvent:
    user_id: str
    platform: str
    product_id: str
    revenue: float
    currency: str
    recommendation_event_id: Optional[str]
    created_at: datetime
