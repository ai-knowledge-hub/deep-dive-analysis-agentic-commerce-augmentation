"""Simple product search tool using DuckDuckGo HTML results."""

from __future__ import annotations

import urllib.parse
import urllib.request
import re


def _fetch(url: str, timeout: int = 8) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "CCO-Research/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(15000)
    return raw.decode("utf-8", errors="ignore")


def _extract_links(html: str, limit: int = 5) -> list[dict]:
    results: list[dict] = []
    # DuckDuckGo HTML results use <a class="result__a" href="...">Title</a>
    pattern = re.compile(r'class="result__a"[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>')
    for url, title in pattern.findall(html):
        if "duckduckgo.com" in url:
            continue
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        if any(r["url"] == url for r in results):
            continue
        results.append({"url": url, "name": clean_title or "Research result"})
        if len(results) >= limit:
            break
    if results:
        return results
    # Fallback: any links
    for match in re.findall(r'href="(https?://[^"]+)"', html):
        if "duckduckgo.com" in match:
            continue
        if any(r["url"] == match for r in results):
            continue
        results.append({"url": match, "name": "Research result"})
        if len(results) >= limit:
            break
    return results


def run(query: str, limit: int = 5, timeout: int = 8) -> dict:
    encoded = urllib.parse.quote_plus(query)
    url = f"https://duckduckgo.com/html/?q={encoded}"
    try:
        html = _fetch(url, timeout=timeout)
        results = _extract_links(html, limit=limit)
        return {"query": query, "results": results, "source": "duckduckgo_html"}
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}


__all__ = ["run"]
