"""Protocol-layer (Layer 2) domain types and pure scoring.

Layer 2 models protocol-based commerce discovery where merchants *declare*
product data via structured feeds/APIs (e.g., ACP/UCP), rather than relying
on inference from web pages.
"""

from domain.protocol.types import (
    ProtocolCandidate,
    ProtocolReadinessIssue,
    ProtocolType,
    StructuredQuery,
)

__all__ = [
    "ProtocolCandidate",
    "ProtocolReadinessIssue",
    "ProtocolType",
    "StructuredQuery",
]
