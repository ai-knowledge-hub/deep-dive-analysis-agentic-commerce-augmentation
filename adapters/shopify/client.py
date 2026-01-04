"""Minimal Shopify Admin API client used by the feed adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, Optional

import requests


@dataclass
class ShopifyConfig:
    shop_domain: str
    token: str
    api_version: str = "2024-01"


class ShopifyClient:
    def __init__(self, config: ShopifyConfig) -> None:
        self.base_url = f"https://{config.shop_domain}/admin/api/{config.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": config.token,
            "Content-Type": "application/json",
        }

    def get_products(self, limit: int = 250) -> Iterator[Dict]:
        url: Optional[str] = f"{self.base_url}/products.json?limit={limit}"
        while url:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            yield from data.get("products", [])
            url = response.links.get("next", {}).get("url")
