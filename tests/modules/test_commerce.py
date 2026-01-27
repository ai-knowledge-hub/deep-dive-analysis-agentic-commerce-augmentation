from domain.commerce.search import related_by_tag, search
from infrastructure.commerce.demo_catalog import load_demo_catalog


def test_search_matches_description():
    catalog = load_demo_catalog()
    results = search(catalog, "ergonomic")
    assert any(product.id == "desk-01" for product in results)


def test_related_by_tag_returns_group():
    catalog = load_demo_catalog()
    related = related_by_tag(catalog, "workspace")
    ids = {product.id for product in related}
    assert {"desk-01", "chair-05"}.issubset(ids)
