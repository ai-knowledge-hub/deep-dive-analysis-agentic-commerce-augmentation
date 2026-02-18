"""Seed demo competitor tenants/brands/products for hackathon scenarios.

This keeps the demo realistic without blocking on real protocol integrations.

Safe to run multiple times (UPSERTs by id).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from shared.db.connection import DEFAULT_DB_PATH, get_connection, init_db
from infrastructure.db.core.json import to_json

PINNED_UCP_VERSION = "2026-01-11"


def _upsert_client(*, client_id: str, name: str, metadata: Dict[str, Any]) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO clients (id, name, metadata_json)
        VALUES (?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            metadata_json = excluded.metadata_json
        """,
        (client_id, name, to_json(metadata) or to_json({})),
    )


def _upsert_brand(
    *, brand_id: str, client_id: str, name: str, metadata: Dict[str, Any]
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO brands (id, client_id, name, metadata_json)
        VALUES (?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            client_id = excluded.client_id,
            name = excluded.name,
            metadata_json = excluded.metadata_json
        """,
        (brand_id, client_id, name, to_json(metadata) or to_json({})),
    )


def _upsert_product(
    *,
    product_id: str,
    brand_id: str,
    name: str,
    description: str,
    metadata: Dict[str, Any],
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO products (id, brand_id, name, description, metadata_json)
        VALUES (?, ?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            brand_id = excluded.brand_id,
            name = excluded.name,
            description = excluded.description,
            metadata_json = excluded.metadata_json
        """,
        (product_id, brand_id, name, description, to_json(metadata) or to_json({})),
    )


def _build_ucp_profile(site_url: str) -> Dict[str, Any]:
    base = site_url.rstrip("/")
    return {
        "ucp": {
            "version": PINNED_UCP_VERSION,
            "services": {
                "dev.ucp.transport.rest": [
                    {
                        "version": PINNED_UCP_VERSION,
                        "id": "rest",
                        "config": {"endpoint": f"{base}/ucp"},
                    }
                ]
            },
            "capabilities": {
                "dev.ucp.shopping.checkout": [
                    {
                        "version": PINNED_UCP_VERSION,
                        "spec": "https://ucp.dev/specification/checkout",
                        "schema": "https://ucp.dev/schemas/shopping/checkout.json",
                    }
                ],
                "dev.ucp.shopping.order": [
                    {
                        "version": PINNED_UCP_VERSION,
                        "spec": "https://ucp.dev/specification/order",
                        "schema": "https://ucp.dev/schemas/shopping/order.json",
                    }
                ],
            },
            "payment_handlers": {},
        }
    }


def seed_demo_competitors() -> Dict[str, int]:
    init_db()
    conn = get_connection()

    scenarios = [
        "achilles-friendly training shoe",
        "flat-feet stability running shoe",
        "lightweight rain running vest",
    ]

    tenants: List[Dict[str, Any]] = [
        {"id": "client-nike", "name": "Nike", "site": "https://www.nike.com"},
        {"id": "client-adidas", "name": "Adidas", "site": "https://www.adidas.com"},
        {
            "id": "client-underarmour",
            "name": "Under Armour",
            "site": "https://www.underarmour.com",
        },
        {
            "id": "client-newbalance",
            "name": "New Balance",
            "site": "https://www.newbalance.com",
        },
        {"id": "client-reebok", "name": "Reebok", "site": "https://www.reebok.com"},
    ]

    product_sets: Dict[str, List[Dict[str, Any]]] = {
        "client-nike": [
            {
                "id": "nike-air-zoom-pegasus",
                "name": "Air Zoom Pegasus (Spec-heavy)",
                "description": "React foam, engineered mesh upper, 10mm drop, rubber outsole.",
                "style": "spec-heavy",
                "scenario": scenarios[1],
            },
            {
                "id": "nike-infinity-run",
                "name": "Infinity Run (Outcome-heavy)",
                "description": "Support long runs with stable cushioning that reduces strain on tired legs.",
                "style": "outcome-heavy",
                "scenario": scenarios[1],
            },
            {
                "id": "nike-structure-25",
                "name": "Structure 25 (Balanced)",
                "description": "Stable daily trainer with supportive fit and cushioning for comfortable miles.",
                "style": "balanced",
                "scenario": scenarios[1],
            },
            {
                "id": "nike-pegasus-trail-vest",
                "name": "Lightweight Running Vest (Outcome-heavy)",
                "description": "Stay visible and dry on wet runs with a lightweight, packable outer layer.",
                "style": "outcome-heavy",
                "scenario": scenarios[2],
            },
            {
                "id": "nike-trail-vest-spec",
                "name": "Running Vest (Spec-heavy)",
                "description": "Ripstop shell, DWR finish, zip pockets, reflective hits, 120g.",
                "style": "spec-heavy",
                "scenario": scenarios[2],
            },
        ],
        "client-adidas": [
            {
                "id": "adidas-ultraboost",
                "name": "Ultraboost (Outcome-heavy)",
                "description": "Soft, responsive cushioning to keep runs comfortable when your joints feel stressed.",
                "style": "outcome-heavy",
                "scenario": scenarios[0],
            },
            {
                "id": "adidas-solar-control",
                "name": "Solar Control (Balanced)",
                "description": "Stability-focused trainer designed to guide your stride and improve comfort.",
                "style": "balanced",
                "scenario": scenarios[1],
            },
            {
                "id": "adidas-adizero-sl",
                "name": "Adizero SL (Spec-heavy)",
                "description": "Lightstrike midsole, engineered mesh, 8.5mm drop, 240g.",
                "style": "spec-heavy",
                "scenario": scenarios[0],
            },
            {
                "id": "adidas-rain-vest",
                "name": "Rain Running Vest (Balanced)",
                "description": "Packable vest that blocks wind and light rain for unpredictable weather runs.",
                "style": "balanced",
                "scenario": scenarios[2],
            },
            {
                "id": "adidas-vest-spec",
                "name": "Running Vest (Spec-heavy)",
                "description": "Poly shell, water-repellent finish, mesh lining, reflective details.",
                "style": "spec-heavy",
                "scenario": scenarios[2],
            },
        ],
        "client-underarmour": [
            {
                "id": "ua-hovr-machina",
                "name": "HOVR Machina (Balanced)",
                "description": "Cushioned ride with supportive feel for steady training runs.",
                "style": "balanced",
                "scenario": scenarios[0],
            },
            {
                "id": "ua-infinite-elite",
                "name": "Infinite Elite (Outcome-heavy)",
                "description": "Protect your Achilles on longer runs with stable cushioning and secure fit.",
                "style": "outcome-heavy",
                "scenario": scenarios[0],
            },
            {
                "id": "ua-trainer-spec",
                "name": "Trainer (Spec-heavy)",
                "description": "Charged midsole, TPU heel counter, 6mm drop, rubber outsole.",
                "style": "spec-heavy",
                "scenario": scenarios[0],
            },
            {
                "id": "ua-storm-vest",
                "name": "UA Storm Running Vest (Outcome-heavy)",
                "description": "Keep essentials close and stay dry in drizzle with a lightweight storm-ready vest.",
                "style": "outcome-heavy",
                "scenario": scenarios[2],
            },
            {
                "id": "ua-storm-vest-spec",
                "name": "UA Storm Vest (Spec-heavy)",
                "description": "UA Storm water-repellent tech, zip pockets, 100% polyester, reflective.",
                "style": "spec-heavy",
                "scenario": scenarios[2],
            },
        ],
        "client-newbalance": [
            {
                "id": "nb-860",
                "name": "860 (Outcome-heavy)",
                "description": "Stability support that helps flat feet feel secure on longer runs.",
                "style": "outcome-heavy",
                "scenario": scenarios[1],
            },
            {
                "id": "nb-1080",
                "name": "1080 (Balanced)",
                "description": "Cushioned daily trainer for comfortable miles and reduced impact feel.",
                "style": "balanced",
                "scenario": scenarios[0],
            },
            {
                "id": "nb-fresh-foam-spec",
                "name": "Fresh Foam Trainer (Spec-heavy)",
                "description": "Fresh Foam X midsole, knit upper, 8mm drop.",
                "style": "spec-heavy",
                "scenario": scenarios[0],
            },
            {
                "id": "nb-rain-vest",
                "name": "Running Vest (Balanced)",
                "description": "Packable layer for wind and light rain; easy to stash mid-run.",
                "style": "balanced",
                "scenario": scenarios[2],
            },
            {
                "id": "nb-rain-vest-spec",
                "name": "Running Vest (Spec-heavy)",
                "description": "Wind-resistant shell, DWR finish, reflective trims, 2 pockets.",
                "style": "spec-heavy",
                "scenario": scenarios[2],
            },
        ],
        "client-reebok": [
            {
                "id": "reebok-floatride-energy",
                "name": "Floatride Energy (Balanced)",
                "description": "Everyday trainer with cushioned comfort for regular runs.",
                "style": "balanced",
                "scenario": scenarios[0],
            },
            {
                "id": "reebok-runner-spec",
                "name": "Runner (Spec-heavy)",
                "description": "EVA midsole, mesh upper, rubber outsole, 9mm drop.",
                "style": "spec-heavy",
                "scenario": scenarios[0],
            },
            {
                "id": "reebok-stability",
                "name": "Stability Trainer (Outcome-heavy)",
                "description": "Stable platform that helps guide your stride and reduce wobble for flat feet.",
                "style": "outcome-heavy",
                "scenario": scenarios[1],
            },
            {
                "id": "reebok-rain-vest",
                "name": "Running Vest (Outcome-heavy)",
                "description": "Stay comfortable in wet wind with a lightweight vest that packs down small.",
                "style": "outcome-heavy",
                "scenario": scenarios[2],
            },
            {
                "id": "reebok-vest-spec",
                "name": "Running Vest (Spec-heavy)",
                "description": "Woven shell, water-repellent finish, reflective, 110g.",
                "style": "spec-heavy",
                "scenario": scenarios[2],
            },
        ],
    }

    created_clients = 0
    created_brands = 0
    created_products = 0

    # Upsert clients and brands
    for tenant in tenants:
        _upsert_client(
            client_id=tenant["id"],
            name=tenant["name"],
            metadata={"site_url": tenant["site"], "category": "sportswear"},
        )
        created_clients += 1

        brand_id = f"brand-{tenant['id'].removeprefix('client-')}"
        _upsert_brand(
            brand_id=brand_id,
            client_id=tenant["id"],
            name=tenant["name"],
            metadata={
                "site_url": tenant["site"],
                "ucp_version": PINNED_UCP_VERSION,
                "ucp_profile_source": "seed",
                "ucp_profile": _build_ucp_profile(tenant["site"]),
                "tone": {
                    "summary": "Clear, performance-led, supportive tone with practical benefits.",
                    "sources": [],
                    "updated_at": None,
                },
                "acp_profile": {
                    "checkout": {
                        "endpoints": {
                            "create_session": f"{tenant['site'].rstrip('/')}/acp/checkout-sessions",
                            "update_session": f"{tenant['site'].rstrip('/')}/acp/checkout-sessions/{{id}}",
                        },
                        "webhooks": [
                            f"{tenant['site'].rstrip('/')}/acp/webhooks/order",
                        ],
                    },
                    "payment": {
                        "delegated": True,
                        "psp": "stripe",
                        "token_constraints": {
                            "max_amount": 500.0,
                            "expires_in_minutes": 15,
                        },
                    },
                },
            },
        )
        created_brands += 1

        for product in product_sets.get(tenant["id"], []):
            updated_at = datetime.now(timezone.utc).isoformat()
            metadata = {
                "demo": True,
                "scenario": product["scenario"],
                "copy_style": product["style"],
                "source": "product",
                "merchant_name": tenant["name"],
                "offer_url": f"{tenant['site'].rstrip('/')}/demo/{product['id']}",
                "product_url": f"{tenant['site'].rstrip('/')}/demo/{product['id']}",
                "creative": {
                    "manual_copy": product["description"],
                    "source_url": f"{tenant['site'].rstrip('/')}/demo/{product['id']}",
                    "last_imported_at": None,
                },
                "availability": "in_stock",
                "price": 99.0,
                "acp": {
                    "item_id": product["id"],
                    "title": product["name"],
                    "description": product["description"],
                    "url": f"{tenant['site'].rstrip('/')}/demo/{product['id']}",
                    "image_url": f"{tenant['site'].rstrip('/')}/demo/{product['id']}.jpg",
                    "price": "99.00 USD",
                    "availability": "in_stock",
                    "brand": tenant["name"],
                    "is_eligible_search": True,
                    "is_eligible_checkout": True,
                    "seller_name": tenant["name"],
                    "seller_url": tenant["site"],
                    "updated_at": updated_at,
                },
                "ucp": {
                    "offer_url": f"{tenant['site'].rstrip('/')}/demo/{product['id']}",
                    "merchant_name": tenant["name"],
                    "price": 99.0,
                    "currency": "USD",
                    "availability": "in_stock",
                    "available_for_sale": True,
                },
            }
            _upsert_product(
                product_id=product["id"],
                brand_id=brand_id,
                name=product["name"],
                description=product["description"],
                metadata=metadata,
            )
            created_products += 1

    conn.commit()
    return {
        "clients": created_clients,
        "brands": created_brands,
        "products": created_products,
    }


def main() -> None:
    counts = seed_demo_competitors()
    db_path = os.getenv("DATABASE_PATH") or str(DEFAULT_DB_PATH)
    print(
        "Seeded demo competitors: "
        f"{counts['clients']} clients, {counts['brands']} brands, {counts['products']} products."
    )
    print(f"Database: {db_path}")
    print("Tip: restart the frontend to refresh tenant lists if needed.")


if __name__ == "__main__":
    # Allow running with custom DB path, e.g. DATABASE_PATH=./tmp/local.db
    os.environ.setdefault("DATABASE_PATH", os.getenv("DATABASE_PATH", "./tmp/local.db"))
    main()
