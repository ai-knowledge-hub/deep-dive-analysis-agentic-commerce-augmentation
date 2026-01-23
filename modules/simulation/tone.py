"""Tone profiling for simulation sandbox."""

from __future__ import annotations

import re
from typing import Dict, List

from modules.simulation.domain import SimulationProduct

_CONTRACTIONS = re.compile(r"\b\w+'(?:t|re|ve|ll|d|m)\b", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"[.!?]+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_ADJECTIVE_SUFFIXES = ("ive", "al", "ous", "ful", "less", "able", "ible", "ic")
_JARGON_RE = re.compile(r"\d|[A-Z]{2,}")


def derive_tone(products: List[SimulationProduct]) -> Dict[str, object]:
    texts = [p.description or p.name for p in products if p.description or p.name]
    if not texts:
        return {"summary": "neutral, concise, plain language"}

    combined = " ".join(texts)
    tokens = _TOKEN_RE.findall(combined)
    words = [token for token in tokens if token.isalpha() or token.isalnum()]
    word_count = max(len(words), 1)

    sentences = [s for s in _SENTENCE_SPLIT.split(combined) if s.strip()]
    sentence_count = max(len(sentences), 1)
    avg_sentence_len = word_count / sentence_count

    contractions = len(_CONTRACTIONS.findall(combined))
    exclamations = combined.count("!")
    casual_score = (contractions + exclamations) / word_count

    adjective_count = sum(
        1
        for word in words
        if word.lower().endswith(_ADJECTIVE_SUFFIXES)
        or word.lower() in {"sleek", "premium", "luxury", "durable", "lightweight"}
    )
    adjective_ratio = adjective_count / word_count

    jargon_count = sum(1 for word in words if _JARGON_RE.search(word))
    jargon_ratio = jargon_count / word_count

    formality = (
        "casual"
        if casual_score > 0.03
        else "formal"
        if avg_sentence_len > 18
        else "neutral"
    )
    sentence_style = (
        "short"
        if avg_sentence_len < 12
        else "medium"
        if avg_sentence_len < 20
        else "long"
    )
    adjective_level = (
        "high"
        if adjective_ratio > 0.08
        else "medium"
        if adjective_ratio > 0.04
        else "low"
    )
    jargon_level = (
        "high" if jargon_ratio > 0.08 else "medium" if jargon_ratio > 0.04 else "low"
    )

    summary = (
        f"{formality}, {sentence_style} sentences, "
        f"{'technical' if jargon_level != 'low' else 'plain'} language, "
        f"{'rich' if adjective_level == 'high' else 'lean'} descriptors"
    )

    return {
        "summary": summary,
        "markers": {
            "formality": formality,
            "sentence_style": sentence_style,
            "adjective_level": adjective_level,
            "jargon_level": jargon_level,
            "avg_sentence_length": round(avg_sentence_len, 1),
        },
    }


__all__ = ["derive_tone"]
