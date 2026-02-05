from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from application.ports.deps import (
    AnalyticsEventsStore,
    AudienceArchetypesStore,
    BrandBeliefsStore,
    ClientsStore,
    QueryBatteriesStore,
    SimulationRunsStore,
)
from application.services.canonical_intent_spec_service import (
    CATEGORY_CONFIDENCE_THRESHOLD,
    infer_category_from_context,
)
from application.services.query_battery_llm_generator import (
    IntentCapsule,
    generate_llm_queries,
)
from application.services.query_battery_types import GeneratedQuery

MIN_BELIEF_CONFIDENCE = 0.65
MIN_ARCHETYPE_CONFIDENCE = 0.6


class QueryBatteryBuilder:
    def __init__(
        self,
        *,
        batteries_repo: QueryBatteriesStore,
        clients_repo: ClientsStore,
        generate_fn: Optional[callable] = None,
        beliefs_repo: BrandBeliefsStore | None = None,
        simulation_runs_repo: SimulationRunsStore | None = None,
        archetypes_repo: AudienceArchetypesStore | None = None,
        analytics_events_repo: AnalyticsEventsStore | None = None,
    ) -> None:
        self._batteries = batteries_repo
        self._clients = clients_repo
        self._generate = generate_fn
        self._beliefs = beliefs_repo
        self._simulation_runs = simulation_runs_repo
        self._archetypes = archetypes_repo
        self._analytics_events = analytics_events_repo

    def generate(
        self,
        *,
        battery_id: str,
        client_id: str,
        source: str,
        seed_queries: Optional[List[str]] = None,
        seed_features: Optional[List[str]] = None,
        seed_use_cases: Optional[List[str]] = None,
        limit: int = 15,
        use_llm: bool = False,
    ) -> List[Dict[str, Any]]:
        created, _ = self.generate_with_report(
            battery_id=battery_id,
            client_id=client_id,
            source=source,
            seed_queries=seed_queries,
            seed_features=seed_features,
            seed_use_cases=seed_use_cases,
            limit=limit,
            use_llm=use_llm,
        )
        return created

    def generate_with_report(
        self,
        *,
        battery_id: str,
        client_id: str,
        source: str,
        seed_queries: Optional[List[str]] = None,
        seed_features: Optional[List[str]] = None,
        seed_use_cases: Optional[List[str]] = None,
        limit: int = 15,
        use_llm: bool = False,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
        capsule = _build_intent_capsule(
            product=product,
            client_id=client_id,
            brand_id=battery.get("brand_id"),
            beliefs_repo=self._beliefs,
            simulation_runs_repo=self._simulation_runs,
            archetypes_repo=self._archetypes,
            allow_description=True,
            seed_features=seed_features,
            seed_use_cases=seed_use_cases,
        )
        bottom_capsule = _build_intent_capsule(
            product=product,
            client_id=client_id,
            brand_id=battery.get("brand_id"),
            beliefs_repo=self._beliefs,
            simulation_runs_repo=self._simulation_runs,
            archetypes_repo=self._archetypes,
            allow_description=False,
            seed_features=seed_features,
            seed_use_cases=seed_use_cases,
        )

        if seed_queries:
            generated.extend(_seed_queries(seed_queries))

        if source in {"top_down", "hybrid"}:
            generated.extend(_top_down_queries(product))
            if use_llm and self._generate:
                banned_terms = _build_banned_terms(product, capsule)
                generated.extend(
                    generate_llm_queries(
                        capsule=capsule,
                        generate_fn=self._generate,
                        limit=max(1, limit),
                        min_per_archetype=1,
                        include_protocol=True,
                        query_type_hint="coverage",
                        banned_terms=banned_terms,
                        include_description=True,
                    )
                )

        if source in {"bottom_up", "hybrid"}:
            generated.extend(_bottom_up_queries(bottom_capsule))
            if use_llm and self._generate:
                banned_terms = _build_banned_terms(product, bottom_capsule)
                generated.extend(
                    generate_llm_queries(
                        capsule=bottom_capsule,
                        generate_fn=self._generate,
                        limit=max(1, limit),
                        min_per_archetype=2
                        if bottom_capsule.audience_archetypes
                        else 1,
                        include_protocol=True,
                        query_type_hint="market",
                        banned_terms=banned_terms,
                        include_description=False,
                    )
                )

        deduped = _dedupe_queries(generated)
        if limit > 0:
            deduped = deduped[:limit]
        category_inference = (
            _infer_category(product.get("metadata") or {}, bottom_capsule)
            if source in {"bottom_up", "hybrid"}
            else {
                "category": None,
                "confidence": 0.0,
                "clarification_required": False,
                "clarification_prompt": None,
                "candidates": [],
            }
        )
        inferred_category = category_inference.get("category")
        clarification_required = bool(category_inference.get("clarification_required"))
        clarification_prompt = category_inference.get("clarification_prompt")
        if source in {"bottom_up", "hybrid"} and clarification_required:
            report = {
                "accepted_count": 0,
                "rejected_count": 0,
                "required_category": inferred_category,
                "category_confidence": category_inference.get("confidence"),
                "category_candidates": category_inference.get("candidates", []),
                "clarification_required": True,
                "clarification_prompt": clarification_prompt,
                "regeneration_count": 0,
                "acceptance_rate": 0.0,
                "rejected": [],
            }
            self._record_eval_event(
                client_id=client_id,
                battery=battery,
                source=source,
                use_llm=use_llm,
                report=report,
            )
            return [], report
        validated, rejected = _validate_queries(
            deduped,
            banned_terms=_build_banned_terms(product, bottom_capsule),
            required_category=inferred_category
            if source in {"bottom_up", "hybrid"}
            else None,
        )
        retried = (
            use_llm
            and self._generate
            and source in {"bottom_up", "hybrid"}
            and len(validated) < max(3, min(limit, 6))
        )
        if retried:
            retry = generate_llm_queries(
                capsule=bottom_capsule,
                generate_fn=self._generate,
                limit=max(1, limit),
                min_per_archetype=1,
                include_protocol=False,
                query_type_hint="market",
                banned_terms=_build_retry_banned_terms(
                    _build_banned_terms(product, bottom_capsule)
                ),
                include_description=False,
            )
            retry_deduped = _dedupe_queries([*validated, *retry])
            validated, rejected_retry = _validate_queries(
                retry_deduped,
                banned_terms=_build_banned_terms(product, bottom_capsule),
                required_category=inferred_category,
            )
            rejected.extend(rejected_retry)

        created: List[Dict[str, Any]] = []
        for item in validated:
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
        acceptance_rate = round((len(validated) / len(deduped)), 4) if deduped else 0.0
        report = {
            "accepted_count": len(validated),
            "rejected_count": len(rejected),
            "required_category": inferred_category,
            "category_confidence": category_inference.get("confidence"),
            "category_candidates": category_inference.get("candidates", []),
            "clarification_required": False,
            "clarification_prompt": None,
            "regeneration_count": 1 if retried else 0,
            "acceptance_rate": acceptance_rate,
            "rejected": rejected[:20],
        }
        self._record_eval_event(
            client_id=client_id,
            battery=battery,
            source=source,
            use_llm=use_llm,
            report=report,
        )
        return created, report

    def _record_eval_event(
        self,
        *,
        client_id: str,
        battery: Dict[str, Any],
        source: str,
        use_llm: bool,
        report: Dict[str, Any],
    ) -> None:
        if not self._analytics_events:
            return
        try:
            self._analytics_events.create_event(
                client_id=client_id,
                brand_id=battery.get("brand_id"),
                product_id=battery.get("product_id"),
                variant_id=None,
                experiment_id=None,
                event_type="query_generation_eval",
                source="battery_builder",
                event_timestamp=None,
                metadata={
                    "battery_id": battery.get("id"),
                    "generation_mode": source,
                    "use_llm": bool(use_llm),
                    "report": report,
                },
            )
        except Exception:
            return


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


def _top_down_queries(product: Dict[str, Any]) -> List[GeneratedQuery]:
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


def _bottom_up_queries(capsule: IntentCapsule) -> List[GeneratedQuery]:
    name = "product"
    intent_labels = capsule.intent_labels or ["everyday use"]
    archetypes = capsule.audience_archetypes or []
    constraints = capsule.constraints or {}
    features = capsule.product_features or []
    use_cases = capsule.use_cases or []
    output: List[GeneratedQuery] = []

    feature_phrase = _build_feature_phrase(features, use_cases, fallback=name)

    for intent in intent_labels[:3]:
        output.append(
            GeneratedQuery(
                query_text=f"best {feature_phrase} for {intent.replace('_', ' ')}",
                query_type="market",
                intent_archetype=archetypes[0] if archetypes else None,
            )
        )
        output.append(
            GeneratedQuery(
                query_text=f"{feature_phrase} for {intent.replace('_', ' ')} with clear benefits",
                query_type="coverage",
                intent_archetype=archetypes[0] if archetypes else None,
            )
        )

    for archetype in archetypes[:3]:
        output.append(
            GeneratedQuery(
                query_text=f"{feature_phrase} for {archetype.lower()} shoppers",
                query_type="market",
                intent_archetype=archetype,
            )
        )

    if constraints.get("availability_required"):
        output.append(
            GeneratedQuery(
                query_text=f"{feature_phrase} available now with fast delivery",
                query_type="protocol",
                constraints={"availability_required": True},
            )
        )
    if constraints.get("budget_sensitive"):
        output.append(
            GeneratedQuery(
                query_text=f"best value {feature_phrase} under budget",
                query_type="market",
                constraints={"budget_sensitive": True},
            )
        )

    return output


def _build_feature_phrase(
    features: List[str],
    use_cases: List[str],
    *,
    fallback: str,
) -> str:
    feature = next((item for item in features if item), "").strip()
    use_case = next((item for item in use_cases if item), "").strip()
    if feature and use_case:
        return f"{feature} {use_case}"
    if feature:
        return feature
    if use_case:
        return use_case
    return fallback


def _build_retry_banned_terms(banned_terms: List[str]) -> List[str]:
    tokens = list(banned_terms)
    for term in banned_terms:
        for token in re.split(r"[\s\-_/,]+", term):
            cleaned = token.strip().lower()
            if len(cleaned) >= 4:
                tokens.append(cleaned)
    return list(dict.fromkeys(tokens))


def _build_banned_terms(
    product: Dict[str, Any],
    capsule: IntentCapsule,
) -> List[str]:
    metadata = product.get("metadata") or {}
    brand = metadata.get("brand") or metadata.get("merchant_name") or ""
    product_name = product.get("name") or ""
    raw_features = capsule.product_features or []
    raw_use_cases = capsule.use_cases or []
    banned: List[str] = []
    for item in [brand, product_name, *raw_features, *raw_use_cases]:
        if isinstance(item, str) and item.strip():
            banned.append(item.strip())
    return banned


def _merge_seed_list(existing: List[str], seeds: Optional[List[str]]) -> List[str]:
    if not seeds:
        return existing
    merged = existing[:]
    for item in seeds:
        if isinstance(item, str) and item.strip():
            merged.append(item.strip())
    return list(dict.fromkeys(merged))


def _build_intent_capsule(
    *,
    product: Dict[str, Any],
    client_id: str,
    brand_id: Optional[str],
    beliefs_repo: BrandBeliefsStore | None,
    simulation_runs_repo: SimulationRunsStore | None,
    archetypes_repo: AudienceArchetypesStore | None,
    allow_description: bool,
    seed_features: Optional[List[str]] = None,
    seed_use_cases: Optional[List[str]] = None,
) -> IntentCapsule:
    metadata = product.get("metadata") or {}
    canonical = (
        metadata.get("canonical_intent_spec")
        if isinstance(metadata.get("canonical_intent_spec"), dict)
        else {}
    )
    name = product.get("name") or "product"
    description = product.get("description") or ""
    features = _extract_features(metadata, description, allow_description)
    use_cases = _extract_use_cases(metadata)
    canonical_features = _to_text_list(canonical.get("feature_concepts"))
    canonical_use_cases = _to_text_list(canonical.get("use_cases"))
    features = canonical_features + features
    use_cases = canonical_use_cases + use_cases
    features = _merge_seed_list(features, seed_features)
    use_cases = _merge_seed_list(use_cases, seed_use_cases)
    constraints = _extract_constraints(metadata)
    archetypes = _extract_archetypes(metadata)
    archetypes.extend(
        _extract_archetypes_from_store(
            archetypes_repo,
            client_id=client_id,
            brand_id=brand_id,
            domain_vertical=metadata.get("vertical") or metadata.get("domain"),
        )
    )
    intent_labels = _extract_intent_labels(metadata)
    canonical_archetypes = _to_text_list(canonical.get("audience_archetypes"))
    archetypes = canonical_archetypes + archetypes
    domain_vertical = (
        canonical.get("category")
        or metadata.get("vertical")
        or metadata.get("domain")
        or metadata.get("category")
    )
    memory_snippets = _extract_memory_snippets(
        beliefs_repo=beliefs_repo,
        simulation_runs_repo=simulation_runs_repo,
        client_id=client_id,
        brand_id=brand_id,
    )
    return IntentCapsule(
        domain_vertical=domain_vertical,
        product_name=name,
        product_description=(description or None) if allow_description else None,
        product_features=features,
        use_cases=use_cases,
        constraints=constraints,
        audience_archetypes=archetypes,
        intent_labels=intent_labels,
        memory_snippets=memory_snippets,
    )


def _extract_features(
    metadata: Dict[str, Any], description: str, allow_description: bool
) -> List[str]:
    features = metadata.get("features")
    if isinstance(features, list):
        return [str(item) for item in features if item]
    if isinstance(features, str):
        return [item.strip() for item in features.split(",") if item.strip()]
    if allow_description and description:
        return [part.strip() for part in description.split(",")[:4] if part.strip()]
    return []


def _extract_use_cases(metadata: Dict[str, Any]) -> List[str]:
    use_case = metadata.get("use_case") or metadata.get("scenario")
    if isinstance(use_case, list):
        return [str(item) for item in use_case if item]
    if isinstance(use_case, str):
        return [item.strip() for item in use_case.split(",") if item.strip()]
    return []


def _to_text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _infer_category(metadata: Dict[str, Any], capsule: IntentCapsule) -> Dict[str, Any]:
    canonical = metadata.get("canonical_intent_spec")
    if isinstance(canonical, dict):
        category = canonical.get("category")
        if isinstance(category, str) and category.strip():
            normalized = category.strip().replace("_", " ")
            return {
                "category": normalized,
                "confidence": 1.0,
                "clarification_required": False,
                "clarification_prompt": None,
                "candidates": [{"category": normalized, "score": 1.0}],
            }
    context_values = [
        *(capsule.product_features or []),
        *(capsule.use_cases or []),
        *(capsule.intent_labels or []),
    ]
    result = infer_category_from_context(
        context_values=context_values,
        explicit_category=None,
        confidence_threshold=CATEGORY_CONFIDENCE_THRESHOLD,
    )
    category = result.get("category")
    if isinstance(category, str):
        result["category"] = category.replace("_", " ")
    candidates = result.get("candidates")
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict) and isinstance(item.get("category"), str):
                item["category"] = item["category"].replace("_", " ")
    return result


def _validate_queries(
    queries: List[GeneratedQuery],
    *,
    banned_terms: List[str],
    required_category: Optional[str],
) -> tuple[List[GeneratedQuery], List[Dict[str, str]]]:
    accepted: List[GeneratedQuery] = []
    rejected: List[Dict[str, str]] = []
    banned = [term.lower() for term in banned_terms if term]
    for item in queries:
        text = item.query_text.strip()
        text_lower = text.lower()
        reason: Optional[str] = None
        if any(term and term in text_lower for term in banned):
            reason = "contains banned term"
        elif re.search(r"\b\d+(\.\d+)?\s?(mm|g|kg|oz|cm|inch|inches)\b", text_lower):
            reason = "over-specific spec token"
        elif required_category and required_category.lower() not in text_lower:
            reason = f"missing category '{required_category}'"
        elif len(text.split()) < 4:
            reason = "query too short"
        if reason:
            rejected.append({"query_text": text, "reason": reason})
        else:
            accepted.append(item)
    return accepted, rejected


def _extract_constraints(metadata: Dict[str, Any]) -> Dict[str, Any]:
    constraints: Dict[str, Any] = {}
    if metadata.get("availability"):
        constraints["availability_required"] = True
    if metadata.get("budget_sensitive"):
        constraints["budget_sensitive"] = True
    if metadata.get("delivery_priority"):
        constraints["delivery_priority"] = metadata.get("delivery_priority")
    return constraints


def _extract_archetypes(metadata: Dict[str, Any]) -> List[str]:
    archetypes = metadata.get("audience_archetypes") or metadata.get("archetypes")
    if isinstance(archetypes, list):
        return [str(item) for item in archetypes if item]
    if isinstance(archetypes, str):
        return [item.strip() for item in archetypes.split(",") if item.strip()]
    return []


def _extract_archetypes_from_store(
    archetypes_repo: AudienceArchetypesStore | None,
    *,
    client_id: str,
    brand_id: Optional[str],
    domain_vertical: Optional[str],
) -> List[str]:
    if not archetypes_repo:
        return []
    try:
        rows = archetypes_repo.list_archetypes(
            client_id=client_id,
            brand_id=brand_id,
            domain_vertical=domain_vertical,
            limit=6,
        )
    except Exception:
        return []
    labels: List[str] = []
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        confidence = metadata.get("confidence")
        if confidence is None and isinstance(row.get("archetype"), dict):
            confidence = row.get("archetype", {}).get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or float(confidence) < MIN_ARCHETYPE_CONFIDENCE
        ):
            continue
        label = row.get("label")
        if isinstance(label, str) and label.strip():
            labels.append(label.strip())
    return labels


def _extract_intent_labels(metadata: Dict[str, Any]) -> List[str]:
    intents = metadata.get("intent_labels") or metadata.get("intent_archetypes")
    if isinstance(intents, list):
        return [str(item) for item in intents if item]
    if isinstance(intents, str):
        return [item.strip() for item in intents.split(",") if item.strip()]
    return []


def _extract_memory_snippets(
    *,
    beliefs_repo: BrandBeliefsStore | None,
    simulation_runs_repo: SimulationRunsStore | None,
    client_id: str,
    brand_id: Optional[str],
) -> List[str]:
    snippets: List[str] = []
    if beliefs_repo and brand_id:
        try:
            beliefs = beliefs_repo.list_beliefs(
                client_id=client_id,
                brand_id=brand_id,
                limit=5,
            )
            for belief in beliefs:
                confidence = belief.get("confidence")
                if (
                    not isinstance(confidence, (int, float))
                    or float(confidence) < MIN_BELIEF_CONFIDENCE
                ):
                    continue
                recommendation = belief.get("recommendation")
                summary = (belief.get("metadata") or {}).get("summary")
                if isinstance(summary, str) and summary.strip():
                    snippets.append(summary.strip())
                elif isinstance(recommendation, str) and recommendation.strip():
                    snippets.append(recommendation.strip())
        except Exception:
            pass
    # Simulation lessons currently do not carry confidence metadata.
    # Keep them out of memory context until confidence scoring is available.
    return snippets


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
