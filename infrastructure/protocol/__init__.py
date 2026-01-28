"""Protocol discovery adapters (ACP/UCP).

These are infrastructure components: they read from the DB today (mock-first),
and later can be swapped to call real merchant endpoints.
"""

from infrastructure.protocol.acp import discover_acp_candidates, validate_acp_candidate
from infrastructure.protocol.ucp import discover_ucp_candidates, validate_ucp_candidate

__all__ = [
    "discover_acp_candidates",
    "discover_ucp_candidates",
    "validate_acp_candidate",
    "validate_ucp_candidate",
]
