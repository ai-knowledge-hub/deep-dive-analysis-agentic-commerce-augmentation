"""Populate canonical intent specs for all existing products.

Usage:
  python -m scripts.seed.seed_canonical_intent_specs
  python -m scripts.seed.seed_canonical_intent_specs --overwrite
  python -m scripts.seed.seed_canonical_intent_specs --dry-run
"""

from __future__ import annotations

import argparse
from typing import Any, Dict

from application.services.admin.canonical_intent_spec_service import (
    CanonicalIntentSpecService,
    DEFAULT_SOURCE_PRIORITY,
)
import infrastructure.db.catalog.clients as clients_repo
from shared.db.connection import DEFAULT_DB_PATH, init_db


def _has_canonical_spec(product: Dict[str, Any]) -> bool:
    metadata = product.get("metadata")
    if not isinstance(metadata, dict):
        return False
    canonical = metadata.get("canonical_intent_spec")
    return isinstance(canonical, dict) and bool(canonical.get("category"))


def run(*, overwrite: bool, dry_run: bool) -> Dict[str, int]:
    init_db()
    service = CanonicalIntentSpecService(clients_repo=clients_repo)

    counts = {
        "clients": 0,
        "brands": 0,
        "products": 0,
        "updated": 0,
        "skipped_existing": 0,
        "clarification_required": 0,
    }
    for client in clients_repo.list_clients():
        counts["clients"] += 1
        client_id = client["id"]
        for brand in clients_repo.list_brands(client_id=client_id):
            counts["brands"] += 1
            brand_id = brand["id"]
            for product in clients_repo.list_products(brand_id=brand_id):
                counts["products"] += 1
                if _has_canonical_spec(product) and not overwrite:
                    counts["skipped_existing"] += 1
                    continue
                result = service.autofill(
                    product_id=product["id"],
                    source_priority=DEFAULT_SOURCE_PRIORITY,
                    apply=not dry_run,
                )
                if result["canonical_spec"].get("clarification_required"):
                    counts["clarification_required"] += 1
                counts["updated"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed canonical intent specs for products"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing canonical_intent_spec if already present",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute mappings without writing to DB",
    )
    args = parser.parse_args()

    counts = run(overwrite=args.overwrite, dry_run=args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"[{mode}] DB: {DEFAULT_DB_PATH}")
    print(
        "clients={clients} brands={brands} products={products} updated={updated} "
        "skipped_existing={skipped_existing} clarification_required={clarification_required}".format(
            **counts
        )
    )


if __name__ == "__main__":
    main()
