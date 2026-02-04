"""SerpAPI-backed search tool for Google results."""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json


def _api_key() -> str | None:
    return os.getenv("SERPAPI_API_KEY")


def run(
    query: str,
    *,
    location: str | None = None,
    gl: str | None = None,
    hl: str | None = None,
    limit: int = 5,
) -> dict:
    api_key = _api_key()
    if not api_key:
        return {"error": "SERPAPI_API_KEY missing."}

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
    }
    if location:
        params["location"] = location
    if gl:
        params["gl"] = gl
    if hl:
        params["hl"] = hl

    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "CCO-Research/1.0"}
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read()
        payload = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}

    results = []
    organic = payload.get("organic_results") or []
    for item in organic:
        link = item.get("link")
        title = item.get("title") or "Search result"
        snippet = item.get("snippet") or ""
        if not link:
            continue
        results.append({"url": link, "name": title, "snippet": snippet})
        if len(results) >= limit:
            break

    return {
        "query": query,
        "results": results,
        "source": "serpapi",
    }


__all__ = ["run"]
