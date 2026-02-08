from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from application.services.evidence.service import EvidenceService


@dataclass(frozen=True)
class Layer1RunConfig:
    max_items: int = 5
    optimize: bool = True
    verify: bool = True


class Layer1Agent:
    """Layer 1 agent (Inference Discovery) - minimal wrapper.

    Strangler approach:
    - Today: deterministic orchestration over existing EvidenceService.
    - Next: replace with tool-driven AgentLoop policy using harness components.
    """

    def __init__(self, *, evidence_service: Optional[EvidenceService] = None) -> None:
        self._evidence = evidence_service or EvidenceService()

    def run(
        self,
        *,
        query: str,
        config: Optional[Layer1RunConfig] = None,
        tone: Optional[str] = None,
        client_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        cfg = config or Layer1RunConfig()

        analyzed = self._evidence.analyze(
            query=query,
            max_items=cfg.max_items,
            client_id=client_id,
            user_id=user_id,
            session_id=session_id,
        )

        optimized: Dict[str, Any] | None = None
        verified: Dict[str, Any] | None = None

        if cfg.optimize:
            optimized = self._evidence.optimize_representation(
                query=query,
                evidence_products=analyzed["evidence_products"],
                tone=tone,
                client_id=client_id,
                user_id=user_id,
                session_id=session_id,
            )

        if cfg.verify:
            verified = self._evidence.verify_recommendations(
                query=query,
                evidence_products=analyzed["evidence_products"],
                optimized=(optimized or {}).get("optimized"),
                client_id=client_id,
                user_id=user_id,
                session_id=session_id,
            )

        return {
            "query": query,
            "tone": tone,
            "analyze": analyzed,
            "optimize": optimized,
            "verify": verified,
        }
