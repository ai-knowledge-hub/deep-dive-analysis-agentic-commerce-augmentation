from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException


def external_agent_error(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    retry_after_seconds: Optional[int] = None,
    trace_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    detail: Dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if retry_after_seconds is not None:
        detail["retry_after_seconds"] = retry_after_seconds
    if trace_id:
        detail["trace_id"] = trace_id
    if context:
        detail["context"] = context
    headers = None
    if retry_after_seconds is not None:
        headers = {
            "Retry-After": str(retry_after_seconds),
            "X-Agent-Poll-Interval-Seconds": str(retry_after_seconds),
        }
    return HTTPException(status_code=status_code, detail=detail, headers=headers)
