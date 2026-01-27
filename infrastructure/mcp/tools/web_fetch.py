"""Restricted web fetch tool with allowlist enforcement."""

from __future__ import annotations

import os
import urllib.request
from urllib.parse import urlparse


def _allowlisted(hostname: str) -> bool:
    allowlist_raw = os.getenv("WEB_FETCH_ALLOWLIST", "").strip()
    if not allowlist_raw:
        return False
    allowlist = [
        entry.strip().lower() for entry in allowlist_raw.split(",") if entry.strip()
    ]
    hostname = hostname.lower()
    return any(
        hostname == entry or hostname.endswith(f".{entry}") for entry in allowlist
    )


def run(url: str, max_chars: int = 5000, timeout: int = 8) -> dict:
    """Fetch a URL if it is allowlisted and return truncated text."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"error": "Only http/https URLs are allowed."}
    if not parsed.hostname:
        return {"error": "URL hostname missing."}
    if not _allowlisted(parsed.hostname):
        return {"error": "Host not in WEB_FETCH_ALLOWLIST."}

    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "CCO-Research/1.0"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(max_chars + 1)
    except Exception as exc:  # pragma: no cover - network/IO errors
        return {"error": str(exc)}

    text = raw.decode("utf-8", errors="ignore")
    truncated = len(raw) > max_chars
    if truncated:
        text = text[:max_chars]

    return {
        "url": url,
        "status": 200,
        "content_type": content_type,
        "text": text,
        "truncated": truncated,
    }


__all__ = ["run"]
