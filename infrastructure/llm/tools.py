"""Infrastructure wrapper for tool schemas + execution.

Canonical implementation currently lives in `llm.tools`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from llm.tools import execute_tool as _execute_tool
from llm.tools import get_llm_tools as _get_llm_tools


def llm_schema() -> List[dict]:
    return _get_llm_tools()


def execute_tool(name: str, args: Dict[str, Any]) -> dict:
    return _execute_tool(name, args)


__all__ = ["llm_schema", "execute_tool"]

