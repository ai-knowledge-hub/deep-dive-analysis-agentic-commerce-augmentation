"""Compatibility shim for evidence verification helpers.

Canonical implementation: `application/services/evidence_verify.py`.
"""

from __future__ import annotations

from application.services.evidence_verify import average_alignment, simulate_actual

__all__ = ["simulate_actual", "average_alignment"]

