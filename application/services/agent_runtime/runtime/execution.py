from __future__ import annotations

import sys
from typing import Any, Dict

from application.services.agent_runtime.capabilities import execute_capability


def execute_runtime_capability(**kwargs: Any) -> Dict[str, Any]:
    runtime_package = sys.modules.get("application.services.agent_runtime.runtime")
    patched = getattr(runtime_package, "execute_capability", execute_capability)
    return patched(**kwargs)


__all__ = ["execute_capability", "execute_runtime_capability"]
