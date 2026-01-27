"""Google Shopping catalog adapters."""

from infrastructure.commerce.adapters.google_shopping.mock_feed import load_catalog
from infrastructure.commerce.adapters.google_shopping.merchant_center import (
    load_catalog as load_merchant_catalog,
)

__all__ = ["load_catalog", "load_merchant_catalog"]
