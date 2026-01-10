"""Keyword-based intent classifier."""

from __future__ import annotations

from typing import Any, Callable, List, Mapping, Tuple

from modules.intent.domain import Intent, IntentDefinition
from modules.intent.taxonomy import INTENT_TAXONOMY


LLMClassifier = Callable[[str], Mapping[str, Any]]


class KeywordClassifier:
    """Lightweight intent classifier using keyword matching."""

    def __init__(self, taxonomy: List[IntentDefinition] | None = None) -> None:
        self.taxonomy = taxonomy or INTENT_TAXONOMY

    def classify(self, text: str) -> Intent:
        """Classify intent using keyword matching."""
        return _keyword_intent(text.lower(), self.taxonomy)


def classify(
    user_text: str,
    llm_fallback: LLMClassifier | None = None,
    llm_threshold: float = 0.55,
) -> Intent:
    """Return an intent via keyword matching, with optional LLM fallback."""
    keyword_result = _keyword_intent(user_text.lower(), INTENT_TAXONOMY)

    if not llm_fallback:
        return keyword_result

    try:
        llm_data = dict(llm_fallback(user_text) or {})
    except Exception:
        return keyword_result

    llm_label = _get_str(llm_data, ["label", "intent"], keyword_result.label)
    llm_confidence = _get_float(llm_data, ["confidence", "score"], 0.0)
    llm_domain = _get_str(llm_data, ["domain"], keyword_result.domain)
    llm_evidence = _get_list(llm_data, ["evidence"], keyword_result.evidence)
    llm_questions = _get_list(llm_data, ["clarifying_questions"], keyword_result.clarifying_questions)
    llm_source = _get_str(llm_data, ["source"], "gemini")

    if llm_label not in {"", "unknown"} and llm_confidence >= llm_threshold:
        return Intent(
            label=llm_label,
            confidence=llm_confidence,
            evidence=llm_evidence,
            domain=llm_domain,
            clarifying_questions=llm_questions,
            source=llm_source,
        )

    return Intent(
        label=keyword_result.label,
        confidence=max(keyword_result.confidence, llm_confidence),
        evidence=llm_evidence or keyword_result.evidence,
        domain=llm_domain or keyword_result.domain,
        clarifying_questions=llm_questions or keyword_result.clarifying_questions,
        source="keyword_fallback",
    )


def _score_definition(user_text: str, definition: IntentDefinition) -> Tuple[float, List[str]]:
    """Score how well user text matches an intent definition."""
    hits = [keyword for keyword in definition.keywords if keyword in user_text]
    if not hits:
        return 0.0, []
    coverage = len(hits) / len(definition.keywords)
    salience = max(user_text.count(keyword) for keyword in hits)
    confidence = min(1.0, 0.4 + 0.5 * coverage + 0.1 * salience)
    return confidence, hits


def _keyword_intent(user_text_lower: str, taxonomy: List[IntentDefinition]) -> Intent:
    """Determine intent from keywords."""
    ranked = [
        (definition, *_score_definition(user_text_lower, definition))
        for definition in taxonomy
    ]
    ranked = [entry for entry in ranked if entry[1] > 0]

    if ranked:
        ranked.sort(key=lambda item: item[1], reverse=True)
        top_definition, confidence, evidence = ranked[0]
        return Intent(
            label=top_definition.label,
            confidence=confidence,
            evidence=evidence,
            domain=top_definition.domain,
            clarifying_questions=top_definition.questions,
            source="keyword",
        )

    return Intent(
        label="unknown",
        confidence=0.1,
        evidence=["insufficient context"],
        domain="unknown",
        clarifying_questions=["What goal are you working toward?", "How can we help?"],
        source="keyword",
    )


def _get_str(data: Mapping[str, Any], keys: List[str], default: str) -> str:
    """Extract string value from dict trying multiple keys."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _get_float(data: Mapping[str, Any], keys: List[str], default: float) -> float:
    """Extract float value from dict trying multiple keys."""
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _get_list(data: Mapping[str, Any], keys: List[str], default: List[str]) -> List[str]:
    """Extract list value from dict trying multiple keys."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
    return default


__all__ = ["classify", "KeywordClassifier", "LLMClassifier"]
