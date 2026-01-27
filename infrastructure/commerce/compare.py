from __future__ import annotations

from typing import Iterable

from domain.commerce.types import Product
from domain.commerce.compare import compare as _compare


def compare(products: Iterable[Product]) -> str:
    return _compare(products)


__all__ = ["compare"]
