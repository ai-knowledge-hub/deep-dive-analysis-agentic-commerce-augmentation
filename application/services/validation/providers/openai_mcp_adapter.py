from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import urlencode

from shared.config.env import Settings


class OpenAIMcpAdapter:
    """Build OpenAI MCP launch contract for provider-orchestrated validation."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def build_launch_contract(
        self,
        *,
        job_id: str,
        provider_run_id: str,
        callback_url: str,
        callback_token: str,
        return_url: Optional[str],
        entity_type: Optional[str],
        provider: Optional[str],
    ) -> Dict[str, object]:
        base = self._settings.openai_mcp_launch_url.rstrip("/")
        params = {
            "integration": "openai_mcp_validation",
            "action": "run_validation",
            "job_id": job_id,
            "provider_run_id": provider_run_id,
            "callback_url": callback_url,
            "callback_token": callback_token,
            "entity_type": str(entity_type or ""),
            "provider": str(provider or "openai"),
        }
        if return_url:
            params["return_url"] = return_url
        launch_url = f"{base}/?{urlencode(params)}"
        setup_params = {
            "integration": "openai_mcp_validation",
            "action": "setup",
        }
        setup_url = f"{base}/?{urlencode(setup_params)}"
        return {
            "launch_url": launch_url,
            "setup_url": setup_url,
            "setup_required": True,
            "instructions": (
                "Connect the MCP integration once in ChatGPT, then rerun from Validation. "
                "Subsequent runs open directly with job context and callback token."
            ),
        }
