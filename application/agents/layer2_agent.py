from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from application.ports.deps import AppDeps
from application.services.protocol_discovery_service import ProtocolDiscoveryService


@dataclass(frozen=True)
class SchemaIssue:
    field: str
    severity: str  # "info" | "warning" | "error"
    message: str


class Layer2Agent:
    """Layer 2 agent (Protocol Discovery) - minimal placeholder.

    For now (hackathon scope), Layer 2 does *not* call real ACP/UCP endpoints.
    It performs lightweight schema/shape validation on "protocol-like"
    product records so we can surface:
    - missing critical commerce fields (url, price, availability)
    - protocol readiness hints (e.g., offer_url/merchant_name)

    This keeps the architecture ready for real protocol tool integrations later.
    """

    def __init__(self, *, deps: AppDeps | None = None) -> None:
        self._deps = deps
        self._protocol_service = (
            ProtocolDiscoveryService(
                discover_acp_fn=deps.protocol_discover_acp,
                discover_ucp_fn=deps.protocol_discover_ucp,
                validate_acp_fn=deps.protocol_validate_acp,
                validate_ucp_fn=deps.protocol_validate_ucp,
            )
            if deps
            else None
        )

    def analyze_products(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for product in products:
            results.append(
                {
                    "id": product.get("id"),
                    "issues": [issue.__dict__ for issue in _validate_product(product)],
                }
            )

        total_errors = sum(
            1
            for item in results
            for issue in item.get("issues", [])
            if issue.get("severity") == "error"
        )
        total_warnings = sum(
            1
            for item in results
            for issue in item.get("issues", [])
            if issue.get("severity") == "warning"
        )

        return {
            "product_count": len(products),
            "schema_checks": results,
            "summary": {
                "errors": total_errors,
                "warnings": total_warnings,
            },
        }

    def discover_protocol_candidates(
        self,
        *,
        client_id: str,
        query: str,
        brand_id: str | None = None,
        protocol: str | None = None,
        limit: int = 10,
        inferred_intent: dict | None = None,
    ) -> Dict[str, Any]:
        """Protocol discovery entrypoint (ACP/UCP mock-first).

        If deps/service isn't configured, returns an empty result so callers can
        degrade gracefully.
        """
        if not self._protocol_service:
            return {
                "structured_query": {"query_text": query},
                "candidates": [],
                "summary": {"count": 0, "errors": 0, "warnings": 0},
            }
        proto = protocol if protocol in {"acp", "ucp"} else None
        return self._protocol_service.discover(
            client_id=client_id,
            query=query,
            protocol=proto,  # type: ignore[arg-type]
            brand_id=brand_id,
            limit=limit,
            inferred_intent=inferred_intent,
        )


def _validate_product(product: Dict[str, Any]) -> List[SchemaIssue]:
    issues: List[SchemaIssue] = []

    def req(field: str, msg: str) -> None:
        if not product.get(field):
            issues.append(SchemaIssue(field=field, severity="error", message=msg))

    def warn(field: str, msg: str) -> None:
        if not product.get(field):
            issues.append(SchemaIssue(field=field, severity="warning", message=msg))

    req("id", "Missing product id.")
    req("name", "Missing product name.")

    # For protocol readiness, these are frequently required or strongly helpful.
    warn(
        "offer_url",
        "Missing offer URL; protocol feeds typically include a landing page URL.",
    )
    warn(
        "merchant_name",
        "Missing merchant name; useful for attribution in protocol feeds.",
    )

    # Commerce basics (soft warnings because evidence-based products might not have them)
    warn("price", "Missing price; hard to compare offers without price.")
    warn("availability", "Missing availability; inventory-aware flows need this.")

    source = product.get("source") or "unknown"
    if source in {"ucp", "acp"}:
        req("offer_url", "Protocol product missing offer_url.")

    return issues


__all__ = ["Layer2Agent"]
