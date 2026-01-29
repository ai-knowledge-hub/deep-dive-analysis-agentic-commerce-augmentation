from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import QueryBatteriesStore


class QueryBatteryService:
    def __init__(self, *, repo: QueryBatteriesStore) -> None:
        self._repo = repo

    def create_battery(
        self,
        *,
        client_id: str,
        product_id: str,
        name: str,
        purpose: Optional[str] = None,
        generation_mode: Optional[str] = None,
        status: str = "draft",
        brand_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._repo.create_battery(
            client_id=client_id,
            product_id=product_id,
            name=name,
            purpose=purpose,
            generation_mode=generation_mode,
            status=status,
            brand_id=brand_id,
        )

    def list_batteries(
        self,
        *,
        client_id: str,
        product_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        return self._repo.list_batteries(
            client_id=client_id,
            product_id=product_id,
            brand_id=brand_id,
            status=status,
            limit=limit,
        )

    def get_battery(
        self, *, battery_id: str, client_id: Optional[str] = None
    ) -> Dict[str, Any] | None:
        return self._repo.get_battery(battery_id=battery_id, client_id=client_id)

    def update_battery(
        self,
        *,
        battery_id: str,
        client_id: str,
        name: Optional[str] = None,
        purpose: Optional[str] = None,
        generation_mode: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any] | None:
        return self._repo.update_battery(
            battery_id=battery_id,
            client_id=client_id,
            name=name,
            purpose=purpose,
            generation_mode=generation_mode,
            status=status,
        )

    def add_query(
        self,
        *,
        battery_id: str,
        query_text: str,
        query_type: Optional[str] = None,
        intent_archetype: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        weight: float = 1.0,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        return self._repo.add_query(
            battery_id=battery_id,
            query_text=query_text,
            query_type=query_type,
            intent_archetype=intent_archetype,
            constraints=constraints,
            weight=weight,
            enabled=enabled,
        )

    def list_queries(self, *, battery_id: str) -> list[Dict[str, Any]]:
        return self._repo.list_queries(battery_id=battery_id)

    def update_query(
        self,
        *,
        query_id: str,
        query_text: Optional[str] = None,
        query_type: Optional[str] = None,
        intent_archetype: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        weight: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> Dict[str, Any] | None:
        return self._repo.update_query(
            query_id=query_id,
            query_text=query_text,
            query_type=query_type,
            intent_archetype=intent_archetype,
            constraints=constraints,
            weight=weight,
            enabled=enabled,
        )

    def get_metrics(self, *, battery_id: str) -> Dict[str, Any]:
        queries = self._repo.list_queries(battery_id=battery_id)
        total = len(queries)
        enabled = len([q for q in queries if q.get("enabled")])
        query_types: Dict[str, int] = {}
        archetypes: Dict[str, int] = {}
        weights: list[float] = []
        normalized = set()

        for q in queries:
            qtype = q.get("query_type") or "unspecified"
            query_types[qtype] = query_types.get(qtype, 0) + 1
            archetype = q.get("intent_archetype") or "unspecified"
            archetypes[archetype] = archetypes.get(archetype, 0) + 1
            weight = q.get("weight")
            if isinstance(weight, (int, float)):
                weights.append(float(weight))
            text = (q.get("query_text") or "").strip().lower()
            if text:
                normalized.add(text)

        avg_weight = (sum(weights) / len(weights)) if weights else None
        unique = len(normalized)
        redundancy = 0.0 if total == 0 else round(1 - (unique / total), 4)
        avg_words = None
        if total:
            word_counts = [len((q.get("query_text") or "").split()) for q in queries]
            avg_words = round(sum(word_counts) / len(word_counts), 2)

        enabled_ratio = 0.0 if total == 0 else round(enabled / total, 4)
        type_diversity = 0.0 if total == 0 else round(len(query_types) / total, 4)
        archetype_diversity = 0.0 if total == 0 else round(len(archetypes) / total, 4)

        quality_score = 100.0
        quality_issues: list[str] = []

        if total < 5:
            quality_score -= 30
            quality_issues.append("Low query count (<5). Add more coverage.")
        elif total < 10:
            quality_score -= 15
            quality_issues.append("Query count is thin. Consider adding more.")

        if redundancy > 0.3:
            quality_score -= redundancy * 50
            quality_issues.append(
                f"High redundancy ({round(redundancy * 100, 1)}%). Deduplicate."
            )

        if enabled_ratio < 0.6:
            quality_score -= 10
            quality_issues.append("Many queries disabled. Enable more coverage.")

        if avg_words is not None and avg_words < 4:
            quality_score -= 15
            quality_issues.append("Queries are very short. Add intent context.")
        elif avg_words is not None and avg_words < 6:
            quality_score -= 5
            quality_issues.append("Queries are short. Add more context.")

        if type_diversity < 0.3 and total > 0:
            quality_score -= 10
            quality_issues.append("Low query type diversity.")

        if archetype_diversity < 0.3 and total > 0:
            quality_score -= 10
            quality_issues.append("Low intent archetype diversity.")

        quality_score = max(0, min(100, round(quality_score)))

        return {
            "total_queries": total,
            "enabled_queries": enabled,
            "unique_queries": unique,
            "redundancy_rate": redundancy,
            "avg_weight": avg_weight,
            "avg_words": avg_words,
            "enabled_ratio": enabled_ratio,
            "type_diversity": type_diversity,
            "archetype_diversity": archetype_diversity,
            "quality_score": quality_score,
            "quality_issues": quality_issues,
            "type_breakdown": query_types,
            "archetype_breakdown": archetypes,
        }

    def delete_query(self, *, query_id: str) -> bool:
        return self._repo.delete_query(query_id=query_id)


__all__ = ["QueryBatteryService"]
