"""Stub image analysis tool for multimodal pipelines."""

from __future__ import annotations


def run(image_url: str | None = None, image_base64: str | None = None) -> dict:
    """Return a placeholder until Gemini vision is wired."""
    if not image_url and not image_base64:
        return {"error": "Provide image_url or image_base64."}
    return {
        "status": "unavailable",
        "message": "Image analysis not configured yet.",
        "image_url": image_url,
    }


__all__ = ["run"]
