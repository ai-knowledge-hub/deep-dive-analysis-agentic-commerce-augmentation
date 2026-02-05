from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from application.ports.deps import ClientsStore

DEFAULT_SOURCE_PRIORITY = ["canonical", "ucp", "acp", "feed", "metadata", "description"]
CATEGORY_CONFIDENCE_THRESHOLD = 0.55

TYPO_MAP = {
    "traner": "trainer",
    "hobbiests": "hobbyists",
    "adizero": "running shoe",
}

PHRASE_SYNONYMS = {
    "heel to toe drop": "heel_to_toe_drop",
    "daily trainer": "daily_training_running_shoes",
}

TOKEN_SYNONYMS = {
    "trainer": "running_shoe",
    "trainers": "running_shoe",
    "shoe": "running_shoe",
    "shoes": "running_shoe",
    "tv": "television",
    "apparel": "sports_apparel",
    "vest": "sports_apparel",
}

CATEGORY_KEYWORDS = {
    "running_shoes": [
        "running_shoe",
        "marathon",
        "road_running",
        "daily_training",
        "heel_to_toe_drop",
        "cushioning",
        "stability",
    ],
    "television": [
        "television",
        "hdr",
        "brightness",
        "screen",
        "gaming",
        "anti_reflective",
        "living_room",
    ],
    "sports_apparel": [
        "sports_apparel",
        "vest",
        "breathability",
        "weather",
        "outdoor",
        "training_top",
        "running_vest",
    ],
}


class CanonicalIntentSpecService:
    def __init__(self, *, clients_repo: ClientsStore) -> None:
        self._clients = clients_repo

    def autofill(
        self,
        *,
        product_id: str,
        source_priority: Optional[List[str]] = None,
        apply: bool = False,
    ) -> Dict[str, Any]:
        product = self._clients.get_product(product_id=product_id)
        if not product:
            raise ValueError("product not found")
        mapping = map_product_to_canonical_spec(
            product=product,
            source_priority=source_priority or DEFAULT_SOURCE_PRIORITY,
        )
        response: Dict[str, Any] = {
            "product_id": product_id,
            "canonical_spec": mapping["canonical_spec"],
            "raw": mapping["raw"],
            "normalized": mapping["normalized"],
            "mapping": mapping["mapping"],
        }
        if apply:
            current_metadata = dict(product.get("metadata") or {})
            current_metadata["canonical_intent_spec"] = mapping["canonical_spec"]
            current_metadata["canonical_intent_spec_raw"] = mapping["raw"]
            current_metadata["canonical_intent_spec_normalized"] = mapping["normalized"]
            current_metadata["canonical_intent_mapping"] = mapping["mapping"]
            updated = self._clients.update_product(
                product_id=product_id,
                description=product.get("description"),
                metadata=current_metadata,
            )
            response["product"] = updated
        return response


def map_product_to_canonical_spec(
    *,
    product: Dict[str, Any],
    source_priority: List[str],
) -> Dict[str, Any]:
    metadata = (
        product.get("metadata") if isinstance(product.get("metadata"), dict) else {}
    )
    description = product.get("description") or ""
    raw_by_source = _build_raw_by_source(metadata=metadata, description=description)
    picks = _select_from_sources(raw_by_source, source_priority)

    normalized = {
        "use_cases": _normalize_list(picks["use_cases"]),
        "audience_archetypes": _normalize_list(picks["audience_archetypes"]),
        "feature_concepts": _normalize_list(picks["feature_concepts"]),
        "core_constraints": _normalize_list(picks["core_constraints"]),
        "must_not_target": _normalize_list(picks["must_not_target"]),
        "objective_keywords": _normalize_list(picks["objective_keywords"]),
        "banned_keywords": _normalize_list(picks["banned_keywords"]),
    }
    explicit_category = picks["category"] or picks["sub_category"]
    category_context = [
        *normalized["feature_concepts"],
        *normalized["use_cases"],
        *normalized["audience_archetypes"],
        *normalized["objective_keywords"],
        _normalize_text(str(explicit_category or "")),
    ]
    category_result = infer_category_from_context(
        context_values=category_context,
        explicit_category=picks["category"],
        confidence_threshold=CATEGORY_CONFIDENCE_THRESHOLD,
    )

    canonical_spec = {
        "category": category_result.get("category") or picks["category"] or "",
        "sub_category": picks["sub_category"] or None,
        "use_cases": normalized["use_cases"],
        "audience_archetypes": normalized["audience_archetypes"],
        "feature_concepts": normalized["feature_concepts"],
        "core_constraints": normalized["core_constraints"],
        "must_not_target": normalized["must_not_target"],
        "objective_keywords": normalized["objective_keywords"],
        "banned_keywords": normalized["banned_keywords"],
        "category_confidence": category_result.get("confidence"),
        "category_candidates": category_result.get("candidates", []),
        "clarification_required": category_result.get("clarification_required", False),
        "clarification_prompt": category_result.get("clarification_prompt"),
        "source": source_priority,
    }
    return {
        "canonical_spec": canonical_spec,
        "raw": picks,
        "normalized": normalized,
        "mapping": {
            "source_priority": source_priority,
            "category_inference": category_result,
            "raw_by_source": raw_by_source,
        },
    }


def infer_category_from_context(
    *,
    context_values: Iterable[str],
    explicit_category: Optional[str] = None,
    confidence_threshold: float = CATEGORY_CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    if explicit_category and explicit_category.strip():
        normalized_explicit = _normalize_text(explicit_category)
        for category in CATEGORY_KEYWORDS:
            if category == normalized_explicit or normalized_explicit in category:
                return {
                    "category": category,
                    "confidence": 1.0,
                    "clarification_required": False,
                    "clarification_prompt": None,
                    "candidates": [{"category": category, "score": 1.0}],
                }
    corpus = " ".join(
        value.strip().lower()
        for value in context_values
        if isinstance(value, str) and value.strip()
    )
    if not corpus:
        return {
            "category": None,
            "confidence": 0.0,
            "clarification_required": True,
            "clarification_prompt": "Select a product category before running bottom-up generation.",
            "candidates": [],
        }
    candidates: list[Dict[str, Any]] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in corpus)
        score = round(hits / max(1, len(keywords)), 4)
        candidates.append({"category": category, "score": score})
    ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
    top = ranked[0] if ranked else {"category": None, "score": 0.0}
    category = top.get("category")
    confidence = float(top.get("score") or 0.0)
    clarification_required = confidence < confidence_threshold
    top_labels = [item["category"] for item in ranked[:3] if item["score"] > 0]
    prompt = None
    if clarification_required:
        suggestions = (
            ", ".join(top_labels)
            if top_labels
            else "running_shoes, television, sports_apparel"
        )
        prompt = (
            "Category confidence is low. Please select the closest category "
            f"before bottom-up generation. Suggested categories: {suggestions}."
        )
    return {
        "category": category if confidence > 0 else None,
        "confidence": confidence,
        "clarification_required": clarification_required,
        "clarification_prompt": prompt,
        "candidates": ranked[:3],
    }


def _build_raw_by_source(
    *, metadata: Dict[str, Any], description: str
) -> Dict[str, Dict[str, Any]]:
    canonical = (
        metadata.get("canonical_intent_spec")
        if isinstance(metadata.get("canonical_intent_spec"), dict)
        else {}
    )
    ucp = metadata.get("ucp") if isinstance(metadata.get("ucp"), dict) else {}
    acp = metadata.get("acp") if isinstance(metadata.get("acp"), dict) else {}
    feed = metadata.get("feed") if isinstance(metadata.get("feed"), dict) else {}
    return {
        "canonical": {
            "category": _as_text(canonical.get("category")),
            "sub_category": _as_text(canonical.get("sub_category")),
            "use_cases": _as_list(canonical.get("use_cases")),
            "audience_archetypes": _as_list(canonical.get("audience_archetypes")),
            "feature_concepts": _as_list(canonical.get("feature_concepts")),
            "core_constraints": _as_list(canonical.get("core_constraints")),
            "must_not_target": _as_list(canonical.get("must_not_target")),
            "objective_keywords": _as_list(canonical.get("objective_keywords")),
            "banned_keywords": _as_list(canonical.get("banned_keywords")),
        },
        "ucp": {
            "category": _first_non_empty(
                _as_text(ucp.get("category")),
                _as_text((ucp.get("attributes") or {}).get("category")),
            ),
            "sub_category": _first_non_empty(
                _as_text(ucp.get("sub_category")),
                _as_text((ucp.get("attributes") or {}).get("sub_category")),
            ),
            "use_cases": _merge_lists(
                _as_list(ucp.get("use_cases")),
                _as_list((ucp.get("attributes") or {}).get("use_cases")),
            ),
            "audience_archetypes": _merge_lists(
                _as_list(ucp.get("audience_archetypes"))
            ),
            "feature_concepts": _merge_lists(
                _as_list(ucp.get("feature_concepts")),
                _as_list((ucp.get("attributes") or {}).get("highlights")),
            ),
            "core_constraints": _as_list(ucp.get("constraints")),
            "must_not_target": _as_list(ucp.get("must_not_target")),
            "objective_keywords": _as_list(ucp.get("objective_keywords")),
            "banned_keywords": _as_list(ucp.get("banned_keywords")),
        },
        "acp": {
            "category": _first_non_empty(
                _as_text(acp.get("category")),
                _as_text((acp.get("attributes") or {}).get("category")),
            ),
            "sub_category": _first_non_empty(
                _as_text(acp.get("sub_category")),
                _as_text((acp.get("attributes") or {}).get("sub_category")),
            ),
            "use_cases": _merge_lists(
                _as_list(acp.get("use_cases")),
                _as_list((acp.get("attributes") or {}).get("use_cases")),
            ),
            "audience_archetypes": _as_list(acp.get("audience_archetypes")),
            "feature_concepts": _merge_lists(
                _as_list(acp.get("feature_concepts")),
                _as_list((acp.get("attributes") or {}).get("features")),
            ),
            "core_constraints": _as_list(acp.get("constraints")),
            "must_not_target": _as_list(acp.get("must_not_target")),
            "objective_keywords": _as_list(acp.get("objective_keywords")),
            "banned_keywords": _as_list(acp.get("banned_keywords")),
        },
        "feed": {
            "category": _first_non_empty(
                _as_text(feed.get("category")),
                _as_text(feed.get("google_product_category")),
            ),
            "sub_category": _as_text(feed.get("product_type")),
            "use_cases": _as_list(feed.get("use_cases")),
            "audience_archetypes": _as_list(feed.get("audience_archetypes")),
            "feature_concepts": _merge_lists(
                _as_list(feed.get("features")),
                _as_list(feed.get("highlights")),
            ),
            "core_constraints": _as_list(feed.get("constraints")),
            "must_not_target": _as_list(feed.get("must_not_target")),
            "objective_keywords": _as_list(feed.get("keywords")),
            "banned_keywords": _as_list(feed.get("banned_keywords")),
        },
        "metadata": {
            "category": _first_non_empty(
                _as_text(metadata.get("vertical")),
                _as_text(metadata.get("domain")),
                _as_text(metadata.get("category")),
            ),
            "sub_category": _as_text(metadata.get("sub_category")),
            "use_cases": _merge_lists(
                _as_list(metadata.get("use_case")),
                _as_list(metadata.get("scenario")),
            ),
            "audience_archetypes": _merge_lists(
                _as_list(metadata.get("audience_archetypes")),
                _as_list(metadata.get("archetypes")),
            ),
            "feature_concepts": _as_list(metadata.get("features")),
            "core_constraints": _as_list(metadata.get("constraints")),
            "must_not_target": _as_list(metadata.get("must_not_target")),
            "objective_keywords": _as_list(metadata.get("intent_labels")),
            "banned_keywords": _as_list(metadata.get("banned_keywords")),
        },
        "description": {
            "category": "",
            "sub_category": "",
            "use_cases": [],
            "audience_archetypes": [],
            "feature_concepts": [
                part.strip() for part in description.split(",") if part.strip()
            ][:5],
            "core_constraints": [],
            "must_not_target": [],
            "objective_keywords": [],
            "banned_keywords": [],
        },
    }


def _select_from_sources(
    raw_by_source: Dict[str, Dict[str, Any]], source_priority: List[str]
) -> Dict[str, Any]:
    selected = {
        "category": "",
        "sub_category": "",
        "use_cases": [],
        "audience_archetypes": [],
        "feature_concepts": [],
        "core_constraints": [],
        "must_not_target": [],
        "objective_keywords": [],
        "banned_keywords": [],
    }
    for source in source_priority:
        payload = raw_by_source.get(source)
        if not payload:
            continue
        if not selected["category"]:
            selected["category"] = payload.get("category") or ""
        if not selected["sub_category"]:
            selected["sub_category"] = payload.get("sub_category") or ""
        for key in [
            "use_cases",
            "audience_archetypes",
            "feature_concepts",
            "core_constraints",
            "must_not_target",
            "objective_keywords",
            "banned_keywords",
        ]:
            selected[key] = _merge_lists(selected[key], _as_list(payload.get(key)))
    return selected


def _normalize_list(values: Iterable[str]) -> List[str]:
    normalized: list[str] = []
    for value in values:
        text = _normalize_text(value)
        if text:
            normalized.append(text)
    return list(dict.fromkeys(normalized))


def _normalize_text(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"(\d+(?:\.\d+)?)\s*mm\s*drop", " heel_to_toe_drop ", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*g\b", " lightweight ", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*kg\b", " heavy_weight ", text)
    text = re.sub(r"[^a-z0-9_ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for phrase, canonical in PHRASE_SYNONYMS.items():
        text = text.replace(phrase, canonical)
    tokens = []
    for token in text.split():
        fixed = TYPO_MAP.get(token, token)
        canonical = TOKEN_SYNONYMS.get(fixed, fixed)
        tokens.append(canonical)
    return " ".join(tokens).strip()


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        chunks = [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]
        return chunks
    return []


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _merge_lists(*collections: Iterable[str]) -> List[str]:
    items: list[str] = []
    for collection in collections:
        for value in collection:
            if isinstance(value, str) and value.strip():
                items.append(value.strip())
    return list(dict.fromkeys(items))


__all__ = [
    "CATEGORY_CONFIDENCE_THRESHOLD",
    "CanonicalIntentSpecService",
    "DEFAULT_SOURCE_PRIORITY",
    "TOKEN_SYNONYMS",
    "TYPO_MAP",
    "infer_category_from_context",
    "map_product_to_canonical_spec",
]
