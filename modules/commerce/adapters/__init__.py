"""Catalog adapters for loading products from various sources."""

from modules.commerce.adapters.loader import load_catalog, register_source

__all__ = ["load_catalog", "register_source"]
