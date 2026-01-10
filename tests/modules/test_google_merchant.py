import os
from pathlib import Path

from modules.commerce.adapters.loader import load_catalog
from modules.commerce.adapters.google_shopping.merchant_center import (
    load_catalog as load_merchant_catalog,
)

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "google_merchant_feed.json"


def test_merchant_center_loader_reads_feed(monkeypatch):
    products = load_merchant_catalog(str(DATA_PATH))
    assert products
    assert all(product.source == "google_merchant" for product in products)


def test_catalog_loader_merchant_source(monkeypatch):
    monkeypatch.setenv("CATALOG_SOURCE", "google_merchant")
    monkeypatch.setenv("GOOGLE_MERCHANT_FEED_PATH", str(DATA_PATH))
    try:
        products = load_catalog()
        assert products and products[0].source == "google_merchant"
    finally:
        monkeypatch.delenv("CATALOG_SOURCE", raising=False)
        monkeypatch.delenv("GOOGLE_MERCHANT_FEED_PATH", raising=False)
