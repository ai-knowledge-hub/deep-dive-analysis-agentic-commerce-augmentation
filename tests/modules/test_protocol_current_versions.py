from __future__ import annotations

from domain.protocol.types import ProtocolCandidate
from infrastructure.protocol.acp import validate_acp_candidate
from infrastructure.protocol.ucp_profile import validate_ucp_profile


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
