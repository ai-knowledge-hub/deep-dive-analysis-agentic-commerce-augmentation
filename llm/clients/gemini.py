"""Re-export from shared.llm.clients.gemini for backward compatibility.

DEPRECATED: Import from shared.llm.clients.gemini instead.
"""

from shared.llm.clients.gemini import GeminiConfig, GeminiLLMClient, get_client

__all__ = ["GeminiConfig", "GeminiLLMClient", "get_client"]
