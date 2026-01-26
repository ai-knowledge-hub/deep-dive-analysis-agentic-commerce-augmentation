from __future__ import annotations

from typing import Any, Dict, List, Sequence, Set

from domain.alignment.keyword import dedupe_keep_order, tokenize


def analyze_gap_tokens(
    *,
    goal: str,
    product_id: str,
    score: float,
    product_text_tokens: Set[str],
    winner_id: str | None = None,
    winner_matched_tokens: Sequence[str] | None = None,
    matched_tokens: Sequence[str] | None = None,
) -> Dict[str, Any]:
    goal_tokens = set(tokenize(goal))
    matched = sorted(goal_tokens & product_text_tokens)
    missing = sorted(goal_tokens - product_text_tokens)

    if matched_tokens is not None:
        matched = list(matched_tokens)
    winner_signals: List[str] = []
    if winner_id and winner_matched_tokens is not None:
        winner_signals = [
            signal for signal in winner_matched_tokens if signal not in matched
        ][:3]

    winner_summary = None
    if winner_id and winner_signals:
        winner_summary = (
            f"Winner highlights {', '.join(winner_signals)} for '{goal}', "
            "while this product doesn't frame it that way."
        )

    severity = severity_for_score(score)
    return {
        "product_id": product_id,
        "goal": goal,
        "score": round(score, 3),
        "matched_signals": matched[:5],
        "missing_signals": missing[:5],
        "winner_id": winner_id,
        "winner_signals": winner_signals,
        "competitor_summary": winner_summary,
        "severity": severity,
        "summary": summary(goal, missing, severity),
    }


def severity_for_score(score: float) -> str:
    if score < 0.35:
        return "high"
    if score < 0.55:
        return "medium"
    return "low"


def summary(goal: str, missing: Sequence[str], severity: str) -> str:
    if not missing:
        return f"Clear coverage of '{goal}'."
    missing_list = ", ".join(list(missing)[:3])
    return f"{severity.title()} gap: missing signals for {missing_list}."


def derive_lessons(goal: str, gaps: List[Dict[str, object]]) -> List[str]:
    lessons: List[str] = []
    for gap in gaps:
        winner_signals = gap.get("winner_signals") or []
        if winner_signals:
            lessons.append(
                f"For '{goal}', emphasize {', '.join(list(winner_signals)[:2])} explicitly."
            )
        missing_signals = gap.get("missing_signals") or []
        if missing_signals:
            lessons.append(
                f"Reframe specs into outcomes: {', '.join(list(missing_signals)[:2])}."
            )
    return dedupe_keep_order([str(item) for item in lessons])[:3]


def tokens_for_product_text(text: str) -> Set[str]:
    return set(tokenize(text))
