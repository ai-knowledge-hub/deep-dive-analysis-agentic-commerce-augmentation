from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class BehavioralSegment:
    label: str
    description: str
    confidence: float
    support: int
    support_ratio: float
    signals: List[str]
    sample_queries: List[str]


def derive_segments_from_events(
    events: Iterable[Dict[str, Any]],
    *,
    llm_generate: Optional[Callable[[str], str]] = None,
    max_segments: int = 4,
) -> List[BehavioralSegment]:
    sessions = _group_sessions(events)
    if not sessions:
        return []

    session_profiles = [_profile_session(records) for records in sessions.values()]
    buckets = _bucket_profiles(session_profiles)
    if not buckets:
        return []

    segments = _build_segments(buckets=buckets, total_sessions=len(session_profiles))
    if not segments:
        return []
    segments = segments[: max(1, max_segments)]

    if llm_generate:
        refined = _refine_segments_with_llm(
            segments=segments, llm_generate=llm_generate
        )
        if refined:
            return refined[: max(1, max_segments)]
    return segments


def _group_sessions(
    events: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    fallback_idx = 0
    for event in events:
        metadata = (
            event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        )
        session_id = _first_text(
            metadata.get("session_id"),
            metadata.get("ga_session_id"),
            metadata.get("google_session_id"),
            metadata.get("conversation_session_id"),
        )
        user_id = _first_text(metadata.get("user_id"), metadata.get("visitor_id"))
        if session_id:
            key = session_id
        elif user_id:
            key = user_id
        else:
            fallback_idx += 1
            key = f"event_{fallback_idx}"
        grouped[key].append(event)
    return grouped


def _profile_session(session_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    queries: List[str] = []
    actions: List[str] = []
    source_hints: List[str] = []
    budget = 0
    urgency = 0
    comparison = 0
    research = 0
    readiness = 0
    exploratory = 0
    time_on_page = 0

    for event in session_events:
        event_type = str(event.get("event_type") or "").lower().strip()
        metadata = (
            event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        )
        query = _first_text(
            metadata.get("query"),
            metadata.get("user_query"),
            metadata.get("search_query"),
            metadata.get("query_text"),
        )
        if query:
            queries.append(query)
            query_lower = query.lower()
            if any(
                token in query_lower for token in ("cheap", "budget", "deal", "under ")
            ):
                budget += 1
            if any(
                token in query_lower for token in ("best", "compare", "vs", "versus")
            ):
                comparison += 1
            if any(
                token in query_lower for token in ("how", "guide", "review", "learn")
            ):
                research += 1
            if any(
                token in query_lower
                for token in ("buy", "in stock", "available now", "delivery")
            ):
                readiness += 1
            if any(
                token in query_lower
                for token in ("ideas", "inspiration", "discover", "browse")
            ):
                exploratory += 1
        if event_type in {"add_to_cart", "begin_checkout", "purchase"}:
            readiness += 2
        if event_type in {"view_item", "view_search_results", "search"}:
            research += 1

        source_hint = _first_text(
            metadata.get("traffic_source"),
            metadata.get("channel"),
            event.get("source"),
        )
        if source_hint:
            source_hints.append(source_hint)
        action_list = metadata.get("actions")
        if isinstance(action_list, list):
            actions.extend(
                [str(item).lower() for item in action_list if str(item).strip()]
            )
        previous_actions = metadata.get("previous_actions")
        if isinstance(previous_actions, str):
            actions.extend(
                [
                    item.strip().lower()
                    for item in previous_actions.split(",")
                    if item.strip()
                ]
            )
        time_candidate = metadata.get("time_on_page")
        if isinstance(time_candidate, (int, float)):
            time_on_page += int(time_candidate)

    if any("filter_price" in action or "sort_price" in action for action in actions):
        budget += 1
    if any("compare" in action for action in actions):
        comparison += 1
    if any("review" in action or "spec" in action for action in actions):
        research += 1
    if any("cart" in action or "checkout" in action for action in actions):
        readiness += 2
    if time_on_page > 240:
        research += 1
    if time_on_page < 30 and queries:
        exploratory += 1
    if any(
        "fast" in query.lower() or "today" in query.lower() or "urgent" in query.lower()
        for query in queries
    ):
        urgency += 1

    return {
        "queries": queries[:8],
        "signals": {
            "budget": budget,
            "urgency": urgency,
            "comparison": comparison,
            "research": research,
            "readiness": readiness,
            "exploratory": exploratory,
        },
        "actions_count": len(actions),
        "source_hints": source_hints[:4],
    }


def _bucket_profiles(
    profiles: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for profile in profiles:
        signals = profile["signals"]
        bucket = "Exploratory Browsers"
        if signals["readiness"] >= max(signals["research"], signals["comparison"], 2):
            bucket = "Urgent Ready-to-Buy"
        elif signals["comparison"] >= max(signals["research"], 2):
            bucket = "Research-Heavy Comparers"
        elif signals["budget"] >= 2:
            bucket = "Budget-Driven Evaluators"
        elif signals["research"] >= 2:
            bucket = "Research-Heavy Comparers"
        buckets[bucket].append(profile)
    return buckets


def _build_segments(
    *,
    buckets: Dict[str, List[Dict[str, Any]]],
    total_sessions: int,
) -> List[BehavioralSegment]:
    descriptions = {
        "Urgent Ready-to-Buy": "Users showing strong purchase momentum and delivery/availability urgency.",
        "Research-Heavy Comparers": "Users systematically comparing options and validating fit before purchasing.",
        "Budget-Driven Evaluators": "Users expressing clear value/price constraints while evaluating alternatives.",
        "Exploratory Browsers": "Users in early-stage discovery with broader exploration behavior.",
    }
    segment_list: List[BehavioralSegment] = []
    for label, profiles in sorted(
        buckets.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    ):
        support = len(profiles)
        if support <= 0:
            continue
        support_ratio = support / max(1, total_sessions)
        avg_signals = _average_signals(profiles)
        dominant_signals = sorted(
            avg_signals.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        signal_labels = [name for name, value in dominant_signals if value > 0]
        confidence = min(
            0.95, 0.45 + (support_ratio * 0.45) + (sum(avg_signals.values()) * 0.03)
        )
        sample_queries = []
        for profile in profiles[:3]:
            sample_queries.extend(profile["queries"][:2])
        sample_queries = list(dict.fromkeys(sample_queries))[:5]
        segment_list.append(
            BehavioralSegment(
                label=label,
                description=descriptions.get(
                    label, "Behavioral segment derived from session context."
                ),
                confidence=round(confidence, 2),
                support=support,
                support_ratio=round(support_ratio, 4),
                signals=signal_labels[:3],
                sample_queries=sample_queries,
            )
        )
    return segment_list


def _average_signals(profiles: List[Dict[str, Any]]) -> Dict[str, float]:
    totals: Dict[str, float] = defaultdict(float)
    for profile in profiles:
        for key, value in profile["signals"].items():
            totals[key] += float(value)
    denominator = max(1, len(profiles))
    return {key: value / denominator for key, value in totals.items()}


def _refine_segments_with_llm(
    *,
    segments: List[BehavioralSegment],
    llm_generate: Callable[[str], str],
) -> List[BehavioralSegment]:
    payload = {
        "task": "refine_audience_segments",
        "segments": [
            {
                "label": item.label,
                "description": item.description,
                "confidence": item.confidence,
                "support": item.support,
                "support_ratio": item.support_ratio,
                "signals": item.signals,
                "sample_queries": item.sample_queries,
            }
            for item in segments
        ],
    }
    prompt = (
        "You are a behavioral segmentation analyst. Refine the labels/descriptions into concise "
        "agentic-commerce audience segments. Keep confidence/support fields unchanged. Return ONLY JSON with "
        '{"segments":[{"label":"...","description":"...","confidence":0.0,"support":0,"support_ratio":0.0,'
        '"signals":["..."],"sample_queries":["..."]}]}\n\n'
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = llm_generate(prompt)
    except Exception:
        return []
    parsed = _parse_llm_segments(raw)
    if not parsed:
        return []
    return parsed


def _parse_llm_segments(raw: str) -> List[BehavioralSegment]:
    if not raw:
        return []
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    rows = payload.get("segments")
    if not isinstance(rows, list):
        return []
    output: List[BehavioralSegment] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        description = str(row.get("description") or "").strip()
        if not label:
            continue
        output.append(
            BehavioralSegment(
                label=label[:80],
                description=description[:300]
                or "Behavioral segment derived from session context.",
                confidence=_safe_float(row.get("confidence"), default=0.6),
                support=int(_safe_float(row.get("support"), default=0)),
                support_ratio=_safe_float(row.get("support_ratio"), default=0.0),
                signals=_string_list(row.get("signals"))[:4],
                sample_queries=_string_list(row.get("sample_queries"))[:5],
            )
        )
    return output


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


__all__ = ["BehavioralSegment", "derive_segments_from_events"]
