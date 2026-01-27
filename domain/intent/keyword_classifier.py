"""Pure keyword-based intent inference with optional LLM fallback."""

from __future__ import annotations

from typing import Any, Callable, List, Mapping, Tuple

from domain.intent.types import InferredIntent, IntentDefinition

LLMClassifier = Callable[[str], Mapping[str, Any]]


class KeywordClassifier:
    """Lightweight intent inference using keyword matching (pure)."""

    def __init__(self, taxonomy: List[IntentDefinition]) -> None:
        self.taxonomy = taxonomy

    def classify(self, text: str) -> InferredIntent:
        return keyword_intent(text.lower(), self.taxonomy)


def classify(
    user_text: str,
    *,
    taxonomy: List[IntentDefinition],
    llm_fallback: LLMClassifier | None = None,
    llm_threshold: float = 0.55,
) -> InferredIntent:
    """Return inferred intent via keyword matching, with optional LLM fallback."""
    keyword_result = keyword_intent(user_text.lower(), taxonomy)

    if not llm_fallback:
        return keyword_result

    try:
        llm_data = dict(llm_fallback(user_text) or {})
    except Exception:
        return keyword_result

    llm_primary = _get_str(
        llm_data,
        ["primary_goal", "goal", "intent", "label"],
        keyword_result.primary_goal,
    )
    llm_confidence = _get_float(llm_data, ["confidence", "score"], 0.0)
    llm_domain = _get_str(llm_data, ["domain"], keyword_result.domain or "")
    llm_secondary = _get_list(
        llm_data, ["secondary_goals"], keyword_result.secondary_goals
    )
    llm_needs = _get_list(
        llm_data, ["underlying_needs"], keyword_result.underlying_needs
    )
    llm_signals = _get_list(
        llm_data, ["context_signals", "evidence"], keyword_result.context_signals
    )
    llm_source = _get_str(llm_data, ["source"], "gemini")

    if (
        llm_primary
        and llm_primary not in {"unknown"}
        and llm_confidence >= llm_threshold
    ):
        return InferredIntent(
            primary_goal=llm_primary,
            secondary_goals=llm_secondary,
            underlying_needs=llm_needs,
            context_signals=llm_signals,
            confidence=llm_confidence,
            domain=llm_domain or None,
            source=llm_source,
        )

    return InferredIntent(
        primary_goal=keyword_result.primary_goal,
        secondary_goals=llm_secondary or keyword_result.secondary_goals,
        underlying_needs=llm_needs or keyword_result.underlying_needs,
        context_signals=llm_signals or keyword_result.context_signals,
        confidence=max(keyword_result.confidence, llm_confidence),
        domain=llm_domain or keyword_result.domain,
        source="keyword_fallback",
    )


def score_definition(
    user_text: str, definition: IntentDefinition
) -> Tuple[float, List[str]]:
    """Score how well user text matches an intent definition."""
    hits = [keyword for keyword in definition.keywords if keyword in user_text]
    if not hits:
        return 0.0, []
    coverage = len(hits) / len(definition.keywords)
    salience = max(user_text.count(keyword) for keyword in hits)
    confidence = min(1.0, 0.4 + 0.5 * coverage + 0.1 * salience)
    return confidence, hits


def keyword_intent(
    user_text_lower: str, taxonomy: List[IntentDefinition]
) -> InferredIntent:
    """Determine intent from keywords."""
    ranked = [(definition, *score_definition(user_text_lower, definition)) for definition in taxonomy]
    ranked = [entry for entry in ranked if entry[1] > 0]

    if ranked:
        ranked.sort(key=lambda item: item[1], reverse=True)
        top_definition, confidence, evidence = ranked[0]
        secondary = [
            definition.label.replace("_", " ")
            for definition, score, _ in ranked[1:3]
            if score > 0
        ]
        context_signals: List[str] = []
        for _, _, hits in ranked[:3]:
            context_signals.extend(hits)
        return InferredIntent(
            primary_goal=top_definition.label.replace("_", " "),
            secondary_goals=secondary,
            underlying_needs=[],
            context_signals=list(dict.fromkeys(context_signals)) or evidence,
            confidence=confidence,
            domain=top_definition.domain,
            source="keyword",
        )

    return InferredIntent(
        primary_goal="unknown",
        secondary_goals=[],
        underlying_needs=[],
        context_signals=["insufficient context"],
        confidence=0.1,
        domain="unknown",
        source="keyword",
    )


def _get_str(data: Mapping[str, Any], keys: List[str], default: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _get_float(data: Mapping[str, Any], keys: List[str], default: float) -> float:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _get_list(
    data: Mapping[str, Any], keys: List[str], default: List[str]
) -> List[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
    return default


__all__ = [
    "LLMClassifier",
    "KeywordClassifier",
    "classify",
    "keyword_intent",
    "score_definition",
]

