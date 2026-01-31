"""Application-layer evidence retriever (open-world product representations)."""

from __future__ import annotations

from typing import Callable, List

from domain.evidence.types import EvidenceProduct


def retrieve(
    query: str,
    max_items: int = 5,
    *,
    run_research_fn: Callable[..., dict],
) -> List[EvidenceProduct]:
    research = run_research_fn(query=query, goals=[query], context=None)
    insights = research.get("insights", []) or []
    if not insights:
        return _fallback_products(query)[:max_items]

    urls = _extract_urls(research.get("tool_outputs", []) or [])
    evidence: List[EvidenceProduct] = []
    for idx, insight in enumerate(insights[:max_items]):
        title = insight.get("title") or insight.get("summary") or f"Evidence {idx + 1}"
        summary = insight.get("summary") or title
        evidence.append(
            EvidenceProduct(
                id=str(insight.get("id") or f"evidence-{idx + 1}"),
                name=str(title),
                description=str(summary),
                source=str(insight.get("source") or "research"),
                url=urls[idx] if idx < len(urls) else None,
                confidence=float(insight.get("confidence") or 0.3),
                raw_text=str(summary),
                metadata={"query": query},
            )
        )

    if not evidence:
        return _fallback_products(query)[:max_items]
    return evidence


def _extract_urls(tool_outputs: List[dict]) -> List[str]:
    urls: List[str] = []
    for entry in tool_outputs:
        output = entry.get("output") or {}
        if not isinstance(output, dict):
            continue
        url = output.get("url")
        if url:
            urls.append(url)
    return urls


def _fallback_products(query: str) -> List[EvidenceProduct]:
    return [
        EvidenceProduct(
            id="fallback-1",
            name="Example product representation",
            description=f"Intent-legible framing for: {query}",
            source="fallback",
            confidence=0.25,
            raw_text=query,
        )
    ]


__all__ = ["retrieve"]
