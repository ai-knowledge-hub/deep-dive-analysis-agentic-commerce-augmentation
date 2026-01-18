"""Re-export from shared.llm.prompts for backward compatibility.

DEPRECATED: Import from shared.llm.prompts instead.
"""

from shared.llm.prompts import (
    INTENT_CLASSIFICATION_PROMPT,
    PRODUCT_REASONING_PROMPT,
    VALUES_CLARIFICATION_PROMPT,
)

__all__ = [
    "INTENT_CLASSIFICATION_PROMPT",
    "PRODUCT_REASONING_PROMPT",
    "VALUES_CLARIFICATION_PROMPT",
]
