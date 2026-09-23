"""Canonical SQLite serialization boundary for portable graph revisions."""

from __future__ import annotations

import json

from domain.workflow.portability import (
    PortabilityGraphRevision,
    PortabilityInvariantError,
    canonical_graph_revision_payload,
    portability_graph_revision_from_payload,
)


def read_sqlite_graph_revision(value: object) -> PortabilityGraphRevision:
    if type(value) is not str:
        raise PortabilityInvariantError("SQLite topology evidence must be JSON")
    try:
        payload = json.loads(value)
        revision = portability_graph_revision_from_payload(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PortabilityInvariantError("SQLite topology evidence is invalid") from exc
    canonical = json.dumps(
        canonical_graph_revision_payload(revision),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    if canonical != value:
        raise PortabilityInvariantError("SQLite topology evidence must be canonical")
    return revision


__all__ = ["read_sqlite_graph_revision"]
