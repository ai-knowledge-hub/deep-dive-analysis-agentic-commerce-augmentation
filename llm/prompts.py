"""Re-export from shared.llm.prompts for backward compatibility.

DEPRECATED: Import from shared.llm.prompts instead.
"""

from shared.llm.prompts import (
    IMPULSE_INTERCEPTION_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    PRODUCT_REASONING_PROMPT,
    REFLECTION_PROMPT,
    VALUES_CLARIFICATION_PROMPT,
)

__all__ = [
    "IMPULSE_INTERCEPTION_PROMPT",
    "INTENT_CLASSIFICATION_PROMPT",
    "PRODUCT_REASONING_PROMPT",
    "REFLECTION_PROMPT",
    "VALUES_CLARIFICATION_PROMPT",
]
