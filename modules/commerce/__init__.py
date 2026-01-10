"""Commerce module - product catalog, search, comparison, and plan building.

This module owns all product-related domain models, services, and adapters.
"""

from modules.commerce.domain import Product, RawProduct, RawOffer
from modules.commerce.search import search, related_by_tag, list_empowerment_scores
from modules.commerce.compare import compare

__all__ = [
    "Product",
    "RawProduct",
    "RawOffer",
    "search",
    "related_by_tag",
    "list_empowerment_scores",
    "compare",
]
