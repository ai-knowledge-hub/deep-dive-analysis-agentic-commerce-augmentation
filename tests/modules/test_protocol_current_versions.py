from __future__ import annotations

from domain.protocol.types import ProtocolCandidate, StructuredQuery
from application.services.admin.protocol_discovery_service import ProtocolDiscoveryService
from infrastructure.protocol.acp import discover_acp_candidates, validate_acp_candidate
from infrastructure.protocol.ucp import discover_ucp_candidates
from infrastructure.protocol.ucp_profile import validate_ucp_profile
from shared.db.connection import init_db, set_database_path


def test_ucp_profile_accepts_current_profile_shape_without_pinned_schema():
    profile = {
        "ucp": {
            "version": "2026-04-08",
            "services": {
                "dev.ucp.shopping": [
                    {
                        "version": "2026-04-08",
                        "spec": "https://ucp.dev/2026-04-08/specification/overview",
                        "transport": "rest",
                        "endpoint": "https://merchant.example/ucp/v1",
                        "schema": "https://ucp.dev/2026-04-08/services/shopping/rest.openapi.json",
                    },
                    {
                        "version": "2026-04-08",
                        "spec": "https://ucp.dev/2026-04-08/specification/overview",
                        "transport": "mcp",
                        "endpoint": "https://merchant.example/ucp/mcp",
                        "schema": "https://ucp.dev/2026-04-08/services/shopping/mcp.openrpc.json",
                    },
                ]
            },
            "capabilities": {
                "dev.ucp.shopping.checkout": [
                    {
                        "version": "2026-04-08",
                        "schema": "https://ucp.dev/2026-04-08/schemas/shopping/checkout.json",
                    }
                ],
                "dev.ucp.shopping.cart": [{"version": "2026-04-08"}],
                "dev.ucp.shopping.order": [{"version": "2026-04-08"}],
            },
            "payment_handlers": {
                "dev.shopify.shop_pay": [
                    {
                        "id": "shop_pay_1",
                        "version": "2026-04-08",
                        "available_instruments": [{"type": "shop_pay"}],
                    }
                ]
            },
        },
        "signing_keys": [
            {
                "kid": "merchant_2026",
                "kty": "EC",
                "use": "sig",
                "alg": "ES256",
            }
        ],
    }

    report = validate_ucp_profile(profile)

    assert report.ok is True
    assert ("dev.ucp.shopping.checkout", "2026-04-08") in report.capabilities
    assert report.rest_endpoint == "https://merchant.example/ucp/v1"
    assert not [issue for issue in report.issues if issue.severity == "error"]


def test_acp_current_checkout_profile_requires_capabilities_and_delegate_payment(
    monkeypatch,
):
    monkeypatch.setattr(
        "infrastructure.protocol.acp.clients_repo.get_brand",
        lambda brand_id: {
            "id": brand_id,
            "metadata": {
                "acp_profile": {
                    "checkout": {
                        "endpoints": {
                            "create_session": "https://merchant.example/acp/sessions",
                            "retrieve_session": "https://merchant.example/acp/sessions/{id}",
                            "update_session": "https://merchant.example/acp/sessions/{id}",
                            "complete_session": "https://merchant.example/acp/sessions/{id}/complete",
                        }
                    },
                    "payment": {
                        "delegated": True,
                        "delegate_payment_endpoint": "https://merchant.example/acp/delegate_payment",
                        "token_constraints": {
                            "expires_in_minutes": 15,
                            "max_amount": 20000,
                        },
                    },
                }
            },
        },
    )
    candidate = ProtocolCandidate(
        id="shoe-1",
        name="Runner Pro",
        description="Daily running shoe.",
        protocol="acp",
        offer_url="https://merchant.example/p/shoe-1",
        price=129,
        availability="in_stock",
        raw={
            "product": {
                "brand_id": "brand-a",
                "metadata": {
                    "acp": {
                        "api_version": "2026-04-17",
                        "item_id": "shoe-1",
                        "title": "Runner Pro",
                        "description": "Daily running shoe.",
                        "url": "https://merchant.example/p/shoe-1",
                        "image_url": "https://merchant.example/shoe-1.jpg",
                        "price": "129 USD",
                        "availability": "in_stock",
                        "brand": "Merchant",
                        "is_eligible_search": True,
                        "is_eligible_checkout": True,
                        "seller_name": "Merchant",
                        "seller_url": "https://merchant.example",
                    }
                },
            }
        },
    )

    issues = validate_acp_candidate(candidate)

    fields = {issue.field for issue in issues}
    assert "api_version" not in fields
    assert "checkout_capabilities" in fields
    assert "delegated_payment" not in fields


def test_ucp_live_catalog_search_normalizes_read_only_candidates(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "ucp-live-catalog.db"
    set_database_path(db_path)
    init_db()

    from infrastructure.db.catalog import clients as clients_repo

    profile = {
        "ucp": {
            "version": "2026-04-08",
            "services": {
                "dev.ucp.shopping": [
                    {
                        "version": "2026-04-08",
                        "spec": "https://ucp.dev/2026-04-08/specification/overview",
                        "transport": "rest",
                        "endpoint": "https://merchant.example/ucp",
                        "schema": "https://ucp.dev/2026-04-08/services/shopping/rest.openapi.json",
                    }
                ]
            },
            "capabilities": {
                "dev.ucp.shopping.checkout": [{"version": "2026-04-08"}],
                "dev.ucp.shopping.catalog.search": [{"version": "2026-04-08"}],
            },
            "payment_handlers": {},
        },
        "signing_keys": [],
    }
    clients_repo.create_client(client_id="client-a", name="Client A")
    clients_repo.create_brand(
        brand_id="brand-a",
        client_id="client-a",
        name="Merchant",
        metadata={
            "ucp": {
                "live_discovery": {
                    "enabled": True,
                    "agent_profile_url": "https://agent.example/profile",
                }
            },
            "ucp_profile": profile,
        },
    )
    monkeypatch.setenv("PROTOCOL_FETCH_ALLOWLIST", "merchant.example")

    class FakeResponse:
        headers = {"content-type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self, _limit):
            return b"""
            {
              "ucp": {"version": "2026-04-08"},
              "products": [
                {
                  "id": "prod_runner",
                  "title": "Blue Runner Pro",
                  "description": {"plain": "Responsive daily running shoe."},
                  "url": "https://merchant.example/products/runner",
                  "price_range": {
                    "min": {"amount": 12000, "currency": "USD"},
                    "max": {"amount": 12000, "currency": "USD"}
                  },
                  "tags": ["running", "road"],
                  "variants": [
                    {
                      "id": "var_runner_10",
                      "title": "Size 10",
                      "price": {"amount": 12000, "currency": "USD"},
                      "availability": {"available": true}
                    }
                  ]
                }
              ]
            }
            """

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = request.data
        captured["ucp_agent"] = request.headers.get("Ucp-agent")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "infrastructure.protocol.ucp_live.urllib.request.urlopen",
        fake_urlopen,
    )

    candidates = discover_ucp_candidates(
        client_id="client-a",
        brand_id="brand-a",
        structured_query=StructuredQuery(
            query_text="blue running shoes",
            price_max=150,
        ),
        limit=5,
    )

    assert captured["url"] == "https://merchant.example/ucp/catalog/search"
    assert b"blue running shoes" in captured["body"]
    assert candidates[0].id == "prod_runner"
    assert candidates[0].name == "Blue Runner Pro"
    assert candidates[0].price == 120
    assert candidates[0].currency == "USD"
    assert candidates[0].available_for_sale is True
    assert candidates[0].raw["source"] == "ucp_catalog_search"


def test_acp_live_product_feed_normalizes_searchable_candidates(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "acp-live-feed.db"
    set_database_path(db_path)
    init_db()

    from infrastructure.db.catalog import clients as clients_repo

    clients_repo.create_client(client_id="client-a", name="Client A")
    clients_repo.create_brand(
        brand_id="brand-a",
        client_id="client-a",
        name="Merchant",
        metadata={
            "acp": {
                "live_discovery": {
                    "enabled": True,
                    "feed_url": "https://merchant.example/acp/products.json",
                }
            }
        },
    )
    monkeypatch.setenv("PROTOCOL_FETCH_ALLOWLIST", "merchant.example")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self, _limit):
            return b"""
            {
              "products": [
                {
                  "id": "sku-runner-blue",
                  "title": "Blue Runner Pro",
                  "description": "Responsive road running shoe.",
                  "link": "https://merchant.example/products/runner",
                  "price": "129.00 USD",
                  "availability": "in_stock",
                  "is_eligible_search": true,
                  "is_eligible_checkout": true,
                  "brand": "Merchant",
                  "color": "blue",
                  "size": "10"
                },
                {
                  "id": "sku-hidden",
                  "title": "Hidden Runner",
                  "description": "Not searchable.",
                  "link": "https://merchant.example/products/hidden",
                  "price": "99.00 USD",
                  "availability": "in_stock",
                  "is_eligible_search": false
                }
              ]
            }
            """

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "infrastructure.protocol.acp_live.urllib.request.urlopen",
        fake_urlopen,
    )

    candidates = discover_acp_candidates(
        client_id="client-a",
        brand_id="brand-a",
        structured_query=StructuredQuery(query_text="blue road running shoe"),
        limit=10,
    )

    assert captured["url"] == "https://merchant.example/acp/products.json"
    assert [candidate.id for candidate in candidates] == ["sku-runner-blue"]
    assert candidates[0].protocol == "acp"
    assert candidates[0].price == 129
    assert candidates[0].currency == "USD"
    assert candidates[0].available_for_sale is True
    assert candidates[0].attributes["color"] == "blue"
    assert candidates[0].raw["source"] == "acp_product_feed"


def test_protocol_discovery_result_exposes_candidate_source_counts():
    candidate = ProtocolCandidate(
        id="sku-1",
        name="Blue Runner",
        description="Road running shoe.",
        protocol="acp",
        price=129,
        availability="in_stock",
        raw={"source": "acp_product_feed"},
    )
    service = ProtocolDiscoveryService(
        discover_acp_fn=lambda **kwargs: [candidate],
        discover_ucp_fn=lambda **kwargs: [],
        validate_acp_fn=lambda candidate: [],
        validate_ucp_fn=lambda candidate: [],
    )

    result = service.discover(client_id="client-a", query="blue running shoe")

    assert result["candidates"][0]["discovery_source"] == "acp_product_feed"
    assert result["summary"]["source_counts"] == {"acp_product_feed": 1}
