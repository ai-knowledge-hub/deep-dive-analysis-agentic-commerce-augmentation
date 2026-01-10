from modules.commerce import search as search_products, related_by_tag


def test_search_matches_description():
    results = search_products("ergonomic")
    assert any(product.id == "desk-01" for product in results)


def test_related_by_tag_returns_group():
    related = related_by_tag("workspace")
    ids = {product.id for product in related}
    assert {"desk-01", "chair-05"}.issubset(ids)
