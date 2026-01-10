"""Load canonical products from Shopify using the adapter pipeline."""

from __future__ import annotations

import os
from typing import List

from modules.commerce.domain import Product
from modules.commerce.adapters.transformers import transform_catalog

from .client import ShopifyClient, ShopifyConfig
from .mapper import iter_raw_products


def load_catalog(domain: str | None = None, token: str | None = None) -> List[Product]:
    domain = domain or os.getenv("SHOPIFY_DOMAIN")
    token = token or os.getenv("SHOPIFY_TOKEN")
    if not domain or not token:
        raise RuntimeError("SHOPIFY_DOMAIN and SHOPIFY_TOKEN must be set to load Shopify catalog")
    config = ShopifyConfig(shop_domain=domain, token=token)
    client = ShopifyClient(config)
    raw_products = [raw_product for raw_product in iter_raw_products(client.get_products())]
    return transform_catalog(raw_products)
