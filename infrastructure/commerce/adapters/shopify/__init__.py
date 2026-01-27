"""Shopify catalog adapter."""

from infrastructure.commerce.adapters.shopify.loader import load_catalog
from infrastructure.commerce.adapters.shopify.client import ShopifyClient, ShopifyConfig

__all__ = ["load_catalog", "ShopifyClient", "ShopifyConfig"]
