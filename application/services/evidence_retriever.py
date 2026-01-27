"""Application-layer evidence retriever (open-world product representations)."""

from __future__ import annotations

import json
import os
from typing import List

from domain.evidence.types import EvidenceProduct
from modules.conversation.research import run_research


def retrieve(query: str, max_items: int = 5) -> List[EvidenceProduct]:
    demo_products = _load_demo_products()
    if demo_products:
        return demo_products[:max_items]

    research = run_research(query=query, goals=[query], context=None)
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
        return (demo_products or _fallback_products(query))[:max_items]
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


def _load_demo_products() -> List[EvidenceProduct]:
    path = os.getenv("EVIDENCE_DEMO_PATH", "data/evidence_demo.json")
    enabled = os.getenv("EVIDENCE_DEMO", "true").lower() == "true"
    if not enabled or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []
    products: List[EvidenceProduct] = []
    for item in payload or []:
        products.append(
            EvidenceProduct(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or "Evidence product"),
                description=str(item.get("description") or ""),
                source=str(item.get("source") or "web"),
                url=item.get("url"),
                price=item.get("price"),
                confidence=float(item.get("confidence") or 0.3),
                raw_text=str(item.get("raw_text") or item.get("description") or ""),
                metadata={"optimized_description": item.get("optimized_description")},
            )
        )
    return products


__all__ = ["retrieve"]

