from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from application.ports.deps import ClientsStore, QueryBatteriesStore


@dataclass(frozen=True)
class GeneratedQuery:
    query_text: str
    query_type: str
    intent_archetype: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    weight: float = 1.0


class QueryBatteryBuilder:
    def __init__(
        self,
        *,
        batteries_repo: QueryBatteriesStore,
        clients_repo: ClientsStore,
        generate_fn: Optional[callable] = None,
    ) -> None:
        self._batteries = batteries_repo
        self._clients = clients_repo
        self._generate = generate_fn

    def generate(
        self,
        *,
        battery_id: str,
        client_id: str,
        source: str,
        seed_queries: Optional[List[str]] = None,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        battery = self._batteries.get_battery(
            battery_id=battery_id, client_id=client_id
        )
        if not battery:
            raise ValueError("battery not found")
        product = self._clients.get_product_for_client(
            client_id=client_id, product_id=battery["product_id"]
        )
        if not product:
            raise ValueError("product not found for client")

        source = source.lower().strip()
        if source not in {"bottom_up", "top_down", "hybrid"}:
            raise ValueError("invalid source")

        generated: List[GeneratedQuery] = []

        if source in {"top_down", "hybrid"}:
            if not seed_queries:
                raise ValueError("seed_queries required for top_down or hybrid")
            generated.extend(_seed_queries(seed_queries))

        if source in {"bottom_up", "hybrid"}:
            generated.extend(_bottom_up_queries(product))

        deduped = _dedupe_queries(generated)
        if limit > 0:
            deduped = deduped[:limit]

        created: List[Dict[str, Any]] = []
        for item in deduped:
            created.append(
                self._batteries.add_query(
                    battery_id=battery_id,
                    query_text=item.query_text,
                    query_type=item.query_type,
                    intent_archetype=item.intent_archetype,
                    constraints=item.constraints,
                    weight=item.weight,
                    enabled=True,
                )
            )
        return created


def _seed_queries(seed_queries: Iterable[str]) -> List[GeneratedQuery]:
    output: List[GeneratedQuery] = []
    for query in seed_queries:
        cleaned = query.strip()
        if not cleaned:
            continue
        output.append(
            GeneratedQuery(
                query_text=cleaned,
                query_type="market",
            )
        )
    return output


def _bottom_up_queries(product: Dict[str, Any]) -> List[GeneratedQuery]:
    name = product.get("name") or "product"
    description = product.get("description") or ""
    metadata = product.get("metadata") or {}
    scenario = metadata.get("scenario") or metadata.get("use_case") or ""
    brand = metadata.get("merchant_name") or metadata.get("brand") or ""

    intent = scenario if scenario else "everyday use"
    brand_prefix = f"{brand} " if brand else ""

    queries = [
        GeneratedQuery(
            query_text=f"best {brand_prefix}{name} for {intent}",
            query_type="coverage",
        ),
        GeneratedQuery(
            query_text=f"{intent} {name} that solves the main pain point",
            query_type="coverage",
        ),
        GeneratedQuery(
            query_text=f"compare {brand_prefix}{name} vs alternatives for {intent}",
            query_type="adversarial",
        ),
        GeneratedQuery(
            query_text=f"{brand_prefix}{name} review for {intent}",
            query_type="coverage",
        ),
        GeneratedQuery(
            query_text=f"{brand_prefix}{name} with instant checkout and in-stock availability",
            query_type="protocol",
            constraints={"availability_required": True},
        ),
        GeneratedQuery(
            query_text=f"{brand_prefix}{name} with fast delivery options for {intent}",
            query_type="protocol",
            constraints={"delivery_priority": "fast"},
        ),
    ]

    if description:
        queries.append(
            GeneratedQuery(
                query_text=f"{brand_prefix}{name} features: {description[:80]}",
                query_type="coverage",
            )
        )

    return queries


def _dedupe_queries(queries: Iterable[GeneratedQuery]) -> List[GeneratedQuery]:
    seen: set[str] = set()
    output: List[GeneratedQuery] = []
    for item in queries:
        key = item.query_text.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


__all__ = ["QueryBatteryBuilder", "GeneratedQuery"]
