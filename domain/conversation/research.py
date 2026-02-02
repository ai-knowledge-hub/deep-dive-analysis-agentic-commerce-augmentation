"""Pure research helpers (no IO).

These functions support the research agent by:
- sanitizing model output
- building lightweight insights
- estimating confidence via heuristics
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Dict, List
import json
from urllib.parse import urlparse


def sanitize_llm_text(text: str) -> str:
    if not text:
        return ""
    if "message{" in text and (
        "<start>assistant" in text or "<tool_call>" in text or "<call>" in text
    ):
        return ""
    cleaned = re.sub(r"</?channel[^>]*>", "", text)
    cleaned = cleaned.replace("<start>assistant", "").replace("</start>", "")
    return cleaned.strip()


def extract_text(response: Dict[str, object] | str | None) -> str:
    if isinstance(response, dict):
        text = str(response.get("content") or response.get("text") or "")
    else:
        text = str(response or "")
    return sanitize_llm_text(text)


def parse_confidence(raw: str) -> float | None:
    match = re.search(r"\b(1(?:\\.0+)?|0(?:\\.\\d+)?)\b", str(raw))
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return max(0.0, min(1.0, value))


def confidence_prompt(
    query: str, goals: List[str], summary: str, tool_summary: str
) -> str:
    goals_block = "\n".join(f"- {goal}" for goal in goals) or "- (no explicit goals)"
    return (
        "You are scoring confidence for research notes.\n"
        "Return a single number between 0 and 1 with no extra text.\n\n"
        f"User query: {query}\n"
        f"Goals:\n{goals_block}\n\n"
        f"Research summary:\n{summary}\n\n"
        f"Tool evidence:\n{tool_summary}\n\n"
        "Score higher only if claims are grounded in evidence and match the goals.\n"
        "If evidence is thin or tool errors occurred, score <= 0.4."
    )


def tool_summary(tool_outputs: List[dict]) -> str:
    lines = []
    for entry in tool_outputs:
        name = entry.get("name", "tool")
        output = entry.get("output") or {}
        if isinstance(output, dict) and output.get("error"):
            lines.append(f"- {name}: error={output.get('error')}")
        elif name == "web_fetch" and isinstance(output, dict):
            lines.append(
                f"- web_fetch: status={output.get('status')} url={output.get('url')}"
            )
        elif name == "serp_search" and isinstance(output, dict):
            results = output.get("results") or []
            lines.append(f"- serp_search: results={len(results)}")
        elif name == "product_search" and isinstance(output, dict):
            results = output.get("results") or []
            lines.append(f"- product_search: results={len(results)}")
        else:
            lines.append(f"- {name}: ok")
    return "\n".join(lines) if lines else "- (no tools)"


def build_insights(
    *,
    response: Dict[str, object] | str,
    confidence: float | None,
    query: str,
    goals: List[str],
    tool_outputs: List[dict],
) -> List[dict]:
    text = extract_text(response)
    parsed = _extract_product_json(text)
    if parsed:
        return parsed
    lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    if lines:
        json_products = _extract_json_products_from_lines(lines)
        if json_products:
            return json_products
        # If tools returned product_search results, use them instead of raw lines.
        fallback = fallback_insights(
            response=response,
            query=query,
            goals=goals,
            tool_outputs=tool_outputs,
            confidence=confidence,
        )
        if fallback:
            return fallback
    if not lines:
        fallback = fallback_insights(
            response=response,
            query=query,
            goals=goals,
            tool_outputs=tool_outputs,
            confidence=confidence,
        )
        if fallback:
            return fallback
        return [
            {
                "id": "research-1",
                "title": "Research summary unavailable",
                "summary": "No grounded research summary was returned by the provider.",
                "confidence": confidence if confidence is not None else 0.25,
                "source": "research",
            }
        ]
    insights: List[dict] = []
    filtered_lines = _filter_prompt_lines(lines)
    for idx, line in enumerate(filtered_lines):
        insights.append(
            {
                "id": f"research-{idx + 1}",
                "title": line if line else "Research insight",
                "summary": line,
                "confidence": confidence if confidence is not None else 0.35,
                "source": "research",
            }
        )
    return insights


def _extract_product_json(text: str) -> List[dict]:
    if not text:
        return []
    candidate = _extract_json_block(text)
    if not candidate:
        return []
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []

    products = []
    if isinstance(parsed, dict):
        products = parsed.get("products") or []
    elif isinstance(parsed, list):
        products = parsed

    insights: List[dict] = []
    for idx, item in enumerate(products):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("title") or "").strip()
        url = str(item.get("source_url") or item.get("url") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not name or not url:
            continue
        insights.append(
            {
                "id": item.get("id") or f"research-{idx + 1}",
                "title": name,
                "summary": summary or name,
                "confidence": item.get("confidence"),
                "source": item.get("source") or "research",
                "url": url,
                "price": item.get("price"),
            }
        )
    return insights


def _extract_json_block(text: str) -> str | None:
    if "```" in text:
        matches = re.findall(r"```(?:json)?\\s*([\\s\\S]*?)```", text)
        for match in matches:
            candidate = match.strip()
            if candidate.startswith("{") or candidate.startswith("["):
                if _is_valid_json(candidate):
                    return candidate
    trimmed = text.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        if _is_valid_json(trimmed):
            return trimmed
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = trimmed.find(start_char)
        end = trimmed.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            candidate = trimmed[start : end + 1]
            if _is_valid_json(candidate):
                return candidate
    return None


def _is_valid_json(candidate: str) -> bool:
    try:
        json.loads(candidate)
        return True
    except json.JSONDecodeError:
        return False


def _filter_prompt_lines(lines: List[str]) -> List[str]:
    filtered: List[str] = []
    prompt_markers = (
        "understood",
        "please provide",
        "once i have",
        "i will return",
        "to deliver",
        "create battery",
    )
    for line in lines:
        lower = line.lower()
        if _looks_like_json_scaffold(lower):
            continue
        if lower.startswith("###"):
            continue
        if lower.startswith("|") and "---" in lower:
            continue
        if any(marker in lower for marker in prompt_markers):
            continue
        if lower.startswith("research insight"):
            continue
        filtered.append(line)
    return filtered


def _looks_like_json_scaffold(line: str) -> bool:
    if line in {"{", "}", "[", "]"}:
        return True
    if line.startswith('"products"') or line.startswith('"notes"'):
        return True
    if line.startswith('"name"') or line.startswith('"price"'):
        return True
    if line.startswith('"source_url"') or line.startswith('"summary"'):
        return True
    return False


def _extract_json_products_from_lines(lines: List[str]) -> List[dict]:
    current: dict = {}
    products: List[dict] = []

    def commit():
        nonlocal current
        if current.get("name") and current.get("url"):
            products.append(
                {
                    "id": current.get("id"),
                    "title": current.get("name"),
                    "summary": current.get("summary") or current.get("name"),
                    "confidence": current.get("confidence"),
                    "source": "research",
                    "url": current.get("url"),
                    "price": current.get("price"),
                }
            )
        current = {}

    for raw in lines:
        line = raw.strip().rstrip(",")
        lower = line.lower()
        if line == "{":
            current = {}
            continue
        if line == "}":
            commit()
            continue
        if lower.startswith('"name"') or lower.startswith("name"):
            current["name"] = _strip_json_value(line)
        elif lower.startswith('"price"') or lower.startswith("price"):
            current["price"] = _strip_json_value(line)
        elif lower.startswith('"source_url"') or lower.startswith("source_url"):
            current["url"] = _strip_json_value(line)
        elif lower.startswith('"summary"') or lower.startswith("summary"):
            current["summary"] = _strip_json_value(line)

    if current:
        commit()
    return products


def _strip_json_value(line: str) -> str:
    if ":" not in line:
        return line.strip().strip('"')
    value = line.split(":", 1)[1].strip().strip(",")
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def fallback_insights(
    *,
    response: Dict[str, object] | str,
    query: str,
    goals: List[str],
    tool_outputs: List[dict],
    confidence: float | None,
) -> List[dict]:
    inferred_conf = confidence if confidence is not None else 0.2
    insights: List[dict] = []
    tool_errors: List[str] = []

    for entry in tool_outputs:
        output = entry.get("output") if isinstance(entry, dict) else None
        if not isinstance(output, dict):
            continue
        if output.get("error"):
            tool_errors.append(str(output.get("error")))
        results = output.get("results")
        if isinstance(results, list) and results:
            for idx, item in enumerate(results[:3]):
                name = item.get("name") or "Research result"
                source = item.get("source") or entry.get("name") or "search"
                url = item.get("url")
                summary = (
                    f"{name} surfaced for intent matching (source: {source})."
                    if not url
                    else f"{name} surfaced for intent matching (source: {source}). {url}"
                )
                insights.append(
                    {
                        "id": f"research-tool-{idx + 1}",
                        "title": name,
                        "summary": summary,
                        "confidence": inferred_conf,
                        "source": "tool",
                    }
                )
            if insights:
                return insights

        text = output.get("text") or output.get("content")
        url = output.get("url")
        if isinstance(text, str) and text.strip():
            snippet = text.strip().splitlines()[0][:160]
            insights.append(
                {
                    "id": "research-web-1",
                    "title": url or "Web source",
                    "summary": snippet,
                    "confidence": inferred_conf,
                    "source": "web",
                }
            )
            return insights

    error = ""
    if isinstance(response, dict):
        error = str(response.get("error") or "").strip()
    if tool_errors:
        error = f"{error} Tool errors: {'; '.join(tool_errors)}".strip()
    summary = (
        f"Research unavailable: {error}"
        if error
        else "Research unavailable; no external sources were fetched."
    )
    goal_hint = ", ".join(goals) if goals else query
    insights.append(
        {
            "id": "research-fallback-1",
            "title": "Research summary unavailable",
            "summary": f"{summary} Focus on: {goal_hint}.",
            "confidence": inferred_conf,
            "source": "fallback",
        }
    )
    return insights


def estimate_confidence_heuristic(
    *,
    query: str,
    goals: List[str],
    response: Dict[str, object] | str | None,
    tool_outputs: List[dict],
) -> tuple[float, dict]:
    text = extract_text(response)
    tool_success = 0
    web_fetch_success = 0
    fetched_texts: List[str] = []
    domains: List[str] = []

    for entry in tool_outputs:
        output = entry.get("output") or {}
        if not isinstance(output, dict):
            continue
        if output.get("error"):
            continue
        tool_success += 1
        if entry.get("name") == "web_fetch":
            if output.get("status") == 200:
                web_fetch_success += 1
            url = output.get("url") or ""
            if url:
                host = urlparse(url).hostname or ""
                if host:
                    domains.append(host.lower())
            fetched_texts.append(str(output.get("text") or ""))
        if entry.get("name") == "product_search":
            results = output.get("results") or []
            if isinstance(results, list) and results:
                tool_success += 1
        if entry.get("name") == "product_compare":
            metadata = output.get("metadata") or []
            if isinstance(metadata, list) and metadata:
                tool_success += 1

    overlap = _goal_overlap_score(text, goals, query)
    coverage_score = _coverage_score(text)
    citation_score = 1.0 if web_fetch_success > 0 else 0.0
    tool_score = min(1.0, tool_success / 2)
    authority_score = _authority_score(domains)
    recency_score = _recency_score(" ".join([text] + fetched_texts))
    diversity_score = _diversity_score(domains)

    weights = {
        "tool": 0.2,
        "citation": 0.2,
        "coverage": 0.15,
        "overlap": 0.2,
        "authority": 0.1,
        "recency": 0.1,
        "diversity": 0.05,
    }

    score = (
        tool_score * weights["tool"]
        + citation_score * weights["citation"]
        + coverage_score * weights["coverage"]
        + overlap * weights["overlap"]
        + authority_score * weights["authority"]
        + recency_score * weights["recency"]
        + diversity_score * weights["diversity"]
    )

    score = max(0.0, min(1.0, score))
    detail = {
        "score": score,
        "components": {
            "tool_success": tool_score,
            "citations": citation_score,
            "coverage": coverage_score,
            "goal_overlap": overlap,
            "authority": authority_score,
            "recency": recency_score,
            "diversity": diversity_score,
        },
        "weights": weights,
        "signals": {
            "domains": sorted(set(domains)),
            "tool_success_count": tool_success,
            "web_fetch_success": web_fetch_success,
        },
    }
    return score, detail


def _goal_overlap_score(text: str, goals: List[str], query: str) -> float:
    tokens = _tokenize(" ".join(goals + [query]))
    if not tokens:
        return 0.0
    text_tokens = _tokenize(text)
    overlap = len(tokens.intersection(text_tokens))
    denom = max(1, min(6, len(tokens)))
    return min(1.0, overlap / denom)


def _coverage_score(text: str) -> float:
    length = len(text.strip())
    if length >= 600:
        return 1.0
    if length >= 300:
        return 0.7
    if length >= 120:
        return 0.4
    return 0.1


def _authority_score(domains: List[str]) -> float:
    if not domains:
        return 0.0
    authoritative = 0
    for domain in domains:
        if (
            domain.endswith(".gov")
            or domain.endswith(".edu")
            or domain.endswith(".ac.uk")
        ):
            authoritative += 1
            continue
        if domain.endswith(".gov.uk") or domain.endswith(".who.int"):
            authoritative += 1
            continue
        if domain.endswith(".nih.gov") or domain.endswith(".cdc.gov"):
            authoritative += 1
            continue
    return min(1.0, authoritative / max(1, len(domains)))


def _recency_score(text: str) -> float:
    current_year = datetime.now(timezone.utc).year
    years = {int(match) for match in re.findall(r"\b(?:19|20)\d{2}\b", text)}
    if not years:
        return 0.0
    if any(year >= current_year - 1 for year in years):
        return 1.0
    if any(year >= current_year - 3 for year in years):
        return 0.6
    return 0.2


def _diversity_score(domains: List[str]) -> float:
    unique = len(set(domains))
    if unique >= 3:
        return 1.0
    if unique == 2:
        return 0.6
    return 0.0


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", text.lower())
    return set(tokens)


__all__ = [
    "build_insights",
    "confidence_prompt",
    "estimate_confidence_heuristic",
    "extract_text",
    "fallback_insights",
    "parse_confidence",
    "sanitize_llm_text",
    "tool_summary",
]
