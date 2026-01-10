"""Utility helpers for text normalisation."""

from __future__ import annotations

import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(value: str | None) -> str | None:
    if not value:
        return None
    without_tags = _TAG_RE.sub(" ", value)
    normalized = " ".join(without_tags.split())
    return unescape(normalized).strip() or None
