from core.schema.offer import RawOffer
from core.transformers.offers import raw_offer_to_raw_product


def test_raw_offer_conversion_preserves_metadata():
    offer = RawOffer(
        source="shopify",
        source_id="variant-1",
        merchant_name="Acme",
        offer_url="https://acme.test/product",
        title="Focus Chair",
        description="Ergonomic chair",
        price=399.0,
        currency="USD",
        availability="in_stock",
        inventory_quantity=5,
        variant_attributes={"sku": "focus-chair"},
        media=["https://example.com/chair.jpg"],
        attributes={"capabilities": ["Posture"], "empowerment_scores": {"physical_agency": 0.8}},
        confidence=0.95,
        completeness=0.9,
    )
    raw_product = raw_offer_to_raw_product(offer)
    assert raw_product.source == "shopify"
    assert raw_product.merchant_name == "Acme"
    assert raw_product.offer_url == "https://acme.test/product"
    assert raw_product.confidence == 0.95
    assert raw_product.attributes["capabilities"] == ["Posture"]
