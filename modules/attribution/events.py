"""In-memory attribution event sink for demos/tests."""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, TypeVar

from .models import ConversionEvent, IntentEvent, RecommendationEvent

T = TypeVar("T", IntentEvent, RecommendationEvent, ConversionEvent)


class EventRecorder:
    def __init__(self) -> None:
        self._events: Dict[str, List[dict]] = {
            "intents": [],
            "recommendations": [],
            "conversions": [],
        }

    def record_intent(self, event: IntentEvent) -> None:
        self._events["intents"].append(asdict(event))

    def record_recommendation(self, event: RecommendationEvent) -> None:
        self._events["recommendations"].append(asdict(event))

    def record_conversion(self, event: ConversionEvent) -> None:
        self._events["conversions"].append(asdict(event))

    def export(self) -> Dict[str, List[dict]]:
        return self._events


def get_default_recorder() -> EventRecorder:
    global _RECORDER
    try:
        return _RECORDER
    except NameError:
        _RECORDER = EventRecorder()
        return _RECORDER
