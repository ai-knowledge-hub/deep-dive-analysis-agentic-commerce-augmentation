"""Helpers for extracting deterministic semantic signals from metafields."""

from __future__ import annotations

from typing import Any, Dict, List

LLM_NAMESPACE = "llm"


def extract_llm_metafields(product: Dict[str, Any]) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    for metafield in product.get("metafields", []):
        if metafield.get("namespace") != LLM_NAMESPACE:
            continue
        key = metafield.get("key")
        value = metafield.get("value")
        attrs[key] = value
    return attrs


def derive_capabilities(attrs: Dict[str, Any]) -> List[str]:
    values = attrs.get("capabilities")
    if isinstance(values, list):
        return [str(value) for value in values]
    if isinstance(values, str) and values:
        return [item.strip() for item in values.split(",") if item.strip()]
    return []
