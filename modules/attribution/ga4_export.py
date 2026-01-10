"""Stub exporter showing how attribution events could be sent to GA4."""

from __future__ import annotations

import json
from pathlib import Path

from .events import get_default_recorder


def export_to_json(path: str | Path) -> None:
    recorder = get_default_recorder()
    Path(path).write_text(json.dumps(recorder.export(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    export_to_json("ga4_events.json")
