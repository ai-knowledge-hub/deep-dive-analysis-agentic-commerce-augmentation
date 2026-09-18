"""Port for the sequential-runtime workflow compatibility projection."""

from __future__ import annotations

from typing import Any, Protocol


class WorkflowCompatibilityStore(Protocol):
    def project_sequential_run(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_sequential_projection(self, **kwargs: Any) -> dict[str, Any] | None: ...

    def record_projection_failure(self, **kwargs: Any) -> dict[str, Any]: ...

    def list_projection_candidates(self, **kwargs: Any) -> list[dict[str, Any]]: ...


__all__ = ["WorkflowCompatibilityStore"]
