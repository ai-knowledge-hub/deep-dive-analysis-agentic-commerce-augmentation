from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from application.agents.layer1_agent import Layer1Agent, Layer1RunConfig
from application.agents.layer2_agent import Layer2Agent


@dataclass(frozen=True)
class OrchestratorConfig:
    run_layer2: bool = True


class OrchestratorAgent:
    """Rule-based orchestrator for Layer 1 + Layer 2.

    Keeps orchestration transparent and deterministic:
    - Always run Layer 1 (inference discovery) for a query.
    - Optionally run Layer 2 (protocol/schema checks) when products include protocol metadata
      are present or when explicitly requested.
    """

    def __init__(
        self,
        *,
        layer1: Optional[Layer1Agent] = None,
        layer2: Optional[Layer2Agent] = None,
    ) -> None:
        self.layer1 = layer1 or Layer1Agent()
        self.layer2 = layer2 or Layer2Agent()

    def run(
        self,
        *,
        query: str,
        products: Optional[List[Dict[str, Any]]] = None,
        tone: Optional[str] = None,
        layer1_config: Optional[Layer1RunConfig] = None,
        config: Optional[OrchestratorConfig] = None,
        client_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        cfg = config or OrchestratorConfig()

        layer1_result = self.layer1.run(
            query=query,
            tone=tone,
            config=layer1_config,
            client_id=client_id,
            user_id=user_id,
            session_id=session_id,
        )

        layer2_result = None
        if cfg.run_layer2 and products:
            if _should_run_layer2(products):
                layer2_result = self.layer2.analyze_products(products)

        return {
            "query": query,
            "tone": tone,
            "layer1": layer1_result,
            "layer2": layer2_result,
        }


def _should_run_layer2(products: List[Dict[str, Any]]) -> bool:
    for product in products:
        source = (product.get("source") or "").lower()
        if source in {"ucp", "acp"}:
            return True
        if product.get("offer_url") or product.get("merchant_name"):
            return True
    return False


__all__ = ["OrchestratorAgent", "OrchestratorConfig"]
