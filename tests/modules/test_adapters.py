from modules.commerce.adapters.loader import load_catalog
from modules.commerce.adapters.google_shopping.mock_feed import (
    load_catalog as load_google_catalog,
)


def test_google_mock_catalog_has_confidence():
    products = load_google_catalog()
    assert products, "Expected mock Google catalog to contain products"
    assert all(product.source == "google_shopping" for product in products)
    assert any(product.confidence < 1 for product in products)


def test_catalog_loader_env_switch(monkeypatch):
    monkeypatch.setenv("CATALOG_SOURCE", "google_shopping")
    try:
        products = load_catalog()
        assert products and products[0].source == "google_shopping"
    finally:
        monkeypatch.delenv("CATALOG_SOURCE", raising=False)
