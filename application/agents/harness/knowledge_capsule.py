from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class KnowledgeCapsule:
    """Agent-scoped knowledge bundle.

    This keeps "what the agent knows" explicit and injectable:
    - prompt templates
    - tool allow-lists
    - version identifiers

    It is intentionally lightweight; richer policy/belief state is a future
    experiment and should not block product iteration.
    """

    name: str
    prompt_templates: Dict[str, str] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)
    version: str = "v1"
