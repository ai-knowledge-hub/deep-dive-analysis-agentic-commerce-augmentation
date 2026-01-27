"""Backward compatibility: re-exports from alignment reasoning."""

from infrastructure.llm.product_reasoner import (
    reason_about_products_default as reason_about_products,
)

__all__ = ["reason_about_products"]
