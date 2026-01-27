from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from infrastructure.db import clients as clients_repo


@dataclass(frozen=True)
class SchemaIssue:
    field: str
    severity: str  # "info" | "warning" | "error"
    message: str


class Layer2Agent:
    """Layer 2 agent (Protocol Discovery) - minimal placeholder.

    For now (hackathon scope), Layer 2 does *not* call real ACP/UCP endpoints.
    It performs lightweight schema/shape validation on "catalog/protocol-like"
    product records so we can surface:
    - missing critical commerce fields (url, price, availability)
    - protocol readiness hints (e.g., offer_url/merchant_name)

    This keeps the architecture ready for real protocol tool integrations later.
    """

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

    def get_catalog_candidates(
        self,
        *,
        client_id: str,
        query: str,
        limit: int = 8,
    ) -> Dict[str, Any]:
        matches = clients_repo.search_products_for_client(
            client_id=client_id, query=query, limit=limit
        )
        candidates: List[Dict[str, Any]] = []
        for match in matches:
            metadata = match.get("metadata") or {}
            candidates.append(
                {
                    "id": match["id"],
                    "name": match["name"],
                    "description": match.get("description") or "",
                    "source": str(metadata.get("source") or "catalog"),
                    "offer_url": metadata.get("offer_url") or metadata.get("url"),
                    "merchant_name": metadata.get("merchant_name"),
                    "price": metadata.get("price"),
                    "availability": metadata.get("availability"),
                    "metadata": metadata,
                }
            )

        return {"client_id": client_id, "query": query, "candidates": candidates}


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
    if source in {"catalog", "shopify", "google_merchant", "ucp", "acp"}:
        # When we *think* it's a catalog record, be a bit stricter.
        req("offer_url", "Catalog/protocol product missing offer_url.")

    return issues


__all__ = ["Layer2Agent"]
