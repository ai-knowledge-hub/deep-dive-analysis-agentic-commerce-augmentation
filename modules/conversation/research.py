"""Research agent scaffold for catalog gaps."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Dict, List
from urllib.parse import urlparse

from shared.llm.gateway import generate, generate_with_tools
from shared.config.env import settings
from llm.tools import get_llm_tools, execute_tool


RESEARCH_PROMPT = """You are a catalog gap research agent.

Goal: Provide neutral discovery research when catalog data is thin.
Return a concise bullet summary with citations, plus risks and uncertainty.
Never fabricate sources. If data is unavailable, say so explicitly.
"""


def run_research(query: str, goals: List[str], context: str | None = None) -> dict:
    """Generate a research bundle using MCP tools (web_fetch, etc.)."""
    context_block = f"\n\nSession context:\n{context}" if context else ""
    goal_block = "\n".join(f"- {goal}" for goal in goals) or "- (no explicit goals)"
    prompt = (
        f"{RESEARCH_PROMPT}{context_block}\n\n"
        f"User goals:\n{goal_block}\n\n"
        f"Research query: {query}\n\n"
        "Use tools if needed, then return:\n"
        "1) Summary bullets with citations\n"
        "2) Risks/uncertainties\n"
        "3) Suggested next clarifying question"
    )

    tool_schema = get_llm_tools()
    response = None
    try:
        if settings.llm_provider == "openrouter" and not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key missing")
        response = generate_with_tools(prompt=prompt, tools=tool_schema)
    except Exception as exc:
        response = {"text": "", "error": str(exc)}

    tool_calls = response.get("tool_calls", []) if isinstance(response, dict) else []
    tool_outputs = []
    for call in tool_calls:
        name = call.get("name")
        args = call.get("args", {})
        tool_outputs.append({"name": name, "output": execute_tool(name, args)})

    confidence, breakdown = _estimate_confidence(
        query=query,
        goals=goals,
        response=response,
        tool_outputs=tool_outputs,
    )

    return {
        "query": query,
        "goals": goals,
        "context_used": bool(context),
        "model_response": response,
        "tool_calls": tool_calls,
        "tool_outputs": tool_outputs,
        "confidence": confidence,
        "confidence_breakdown": breakdown,
        "insights": _build_insights(response, confidence),
    }


def _build_insights(
    response: Dict[str, object] | str, confidence: float | None
) -> List[dict]:
    text = _extract_text(response)

    lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    insights = []
    if not lines:
        return [
            {
                "id": "research-1",
                "title": "Research summary unavailable",
                "summary": "No grounded research summary was returned by the provider.",
                "confidence": confidence if confidence is not None else 0.25,
                "source": "research",
            }
        ]
    for idx, line in enumerate(lines):
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


def _extract_text(response: Dict[str, object] | str | None) -> str:
    if isinstance(response, dict):
        text = str(response.get("content") or response.get("text") or "")
    else:
        text = str(response or "")
    return _sanitize_llm_text(text)


def _sanitize_llm_text(text: str) -> str:
    if not text:
        return ""
    if "message{" in text and (
        "<start>assistant" in text or "<tool_call>" in text or "<call>" in text
    ):
        return ""
    cleaned = re.sub(r"</?channel[^>]*>", "", text)
    cleaned = cleaned.replace("<start>assistant", "").replace("</start>", "")
    return cleaned.strip()


def _estimate_confidence(
    query: str,
    goals: List[str],
    response: Dict[str, object] | str | None,
    tool_outputs: List[dict],
) -> tuple[float, dict]:
    heuristic_score, heuristic_detail = _heuristic_confidence(
        query=query, goals=goals, response=response, tool_outputs=tool_outputs
    )
    llm_score, llm_detail = _llm_confidence(
        query=query,
        goals=goals,
        response=response,
        tool_outputs=tool_outputs,
    )

    if llm_score is None:
        blended = heuristic_score
        llm_weight = 0.0
    else:
        llm_weight = 0.3
        blended = (0.7 * heuristic_score) + (llm_weight * llm_score)

    blended = max(0.0, min(1.0, blended))
    return blended, {
        "heuristic": heuristic_detail,
        "llm": llm_detail,
        "blended": blended,
    }


def _heuristic_confidence(
    query: str,
    goals: List[str],
    response: Dict[str, object] | str | None,
    tool_outputs: List[dict],
) -> tuple[float, dict]:
    text = _extract_text(response)
    tool_success = 0
    web_fetch_success = 0
    fetched_texts = []
    domains = []

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

    goal_overlap = _goal_overlap_score(text, goals, query)
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
        + goal_overlap * weights["overlap"]
        + authority_score * weights["authority"]
        + recency_score * weights["recency"]
        + diversity_score * weights["diversity"]
    )

    detail = {
        "score": max(0.0, min(1.0, score)),
        "components": {
            "tool_success": tool_score,
            "citations": citation_score,
            "coverage": coverage_score,
            "goal_overlap": goal_overlap,
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
    return detail["score"], detail


def _llm_confidence(
    query: str,
    goals: List[str],
    response: Dict[str, object] | str | None,
    tool_outputs: List[dict],
) -> tuple[float | None, dict]:
    if settings.llm_provider == "openrouter" and not settings.openrouter_api_key:
        return None, {"status": "skipped", "reason": "openrouter_api_key missing"}
    if settings.llm_provider == "gemini" and not settings.gemini_api_key:
        return None, {"status": "skipped", "reason": "gemini_api_key missing"}

    text = _extract_text(response)
    tool_summary = _tool_summary(tool_outputs)
    prompt = _confidence_prompt(query, goals, text, tool_summary)
    try:
        raw = generate(prompt)
    except Exception as exc:
        return None, {"status": "error", "reason": str(exc)}

    score = _parse_confidence(raw)
    if score is None:
        return None, {"status": "invalid", "raw": str(raw)}

    return score, {"status": "ok", "score": score, "raw": str(raw).strip()}


def _confidence_prompt(
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


def _parse_confidence(raw: str) -> float | None:
    match = re.search(r"\b(1(?:\\.0+)?|0(?:\\.\\d+)?)\b", str(raw))
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return max(0.0, min(1.0, value))


def _tool_summary(tool_outputs: List[dict]) -> str:
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
        elif name == "product_search" and isinstance(output, dict):
            results = output.get("results") or []
            lines.append(f"- product_search: results={len(results)}")
        else:
            lines.append(f"- {name}: ok")
    return "\n".join(lines) if lines else "- (no tools)"


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
    current_year = datetime.utcnow().year
    years = {int(match) for match in re.findall(r"\b(?:19|20)\\d{2}\b", text)}
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


__all__ = ["run_research"]
