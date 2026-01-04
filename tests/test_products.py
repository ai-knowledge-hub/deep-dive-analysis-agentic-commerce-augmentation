from src.products import search as product_search


def test_search_matches_description():
    results = product_search.search("ergonomic")
    assert any(product.id == "desk-01" for product in results)


def test_related_by_tag_returns_group():
    related = product_search.related_by_tag("workspace")
    ids = {product.id for product in related}
    assert {"desk-01", "chair-05"}.issubset(ids)
