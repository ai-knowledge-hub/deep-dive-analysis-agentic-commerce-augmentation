from modules.commerce import search as search_products, related_by_tag
from modules.commerce.adapters.mock import load_catalog as load_mock_catalog
import modules.commerce.search as search_module


def test_search_matches_description(monkeypatch):
    monkeypatch.setattr(search_module, "CATALOG", load_mock_catalog())
    results = search_products("ergonomic")
    assert any(product.id == "desk-01" for product in results)


def test_related_by_tag_returns_group(monkeypatch):
    monkeypatch.setattr(search_module, "CATALOG", load_mock_catalog())
    related = related_by_tag("workspace")
    ids = {product.id for product in related}
    assert {"desk-01", "chair-05"}.issubset(ids)
