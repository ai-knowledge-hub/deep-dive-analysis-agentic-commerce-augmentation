"""Re-export from shared.llm.clients.openrouter for backward compatibility.

DEPRECATED: Import from shared.llm.clients.openrouter instead.
"""

from shared.llm.clients.openrouter import OpenRouterConfig, OpenRouterLLMClient, get_client

__all__ = ["OpenRouterConfig", "OpenRouterLLMClient", "get_client"]
