from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol

from fastapi import HTTPException

from application.ports.deps import AppDeps
from application.services.experiment_orchestrator import ExperimentOrchestrator
from application.services.experiment_runner import ExperimentRunner
from application.services.context_builder import context_for
from application.services.session_manager import SessionManager
from domain.intent.goals import extract_intent_goals


class _GoalAgent(Protocol):
    def start(self, query: str, metadata: dict) -> Any: ...

    def continue_dialogue(self, state: Any, message: str) -> Any: ...


class _IntentAgent(Protocol):
    def detect_intent(
        self, utterance: str, manager: SessionManager | None = None
    ) -> dict: ...


class _CommerceAgent(Protocol):
    def build_plan(
        self, intent: dict, goals: List[str], context: str | None = None
    ) -> dict: ...


class _ExplainAgent(Protocol):
    def explain(self, products: list) -> str: ...


class ConversationService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._orchestrator = ExperimentOrchestrator(deps=deps)
        self._experiment_runner = ExperimentRunner(deps=deps)

    def start(
        self,
        *,
        user_id: str | None,
        client_id: str,
        brand_id: str | None,
        opening_message: str | None,
        metadata: dict | None,
        clarified_goals: list | None,
        goal_agent: _GoalAgent,
        intent_agent: _IntentAgent,
        commerce_agent: _CommerceAgent,
        explain_agent: _ExplainAgent,
        run_research_fn: Callable[..., dict],
        score_alignment_fn: Callable[[List[str], list], list],
        build_profile_with_llm_fn: Callable[[Any], Any],
    ) -> Dict[str, Any]:
        manager = SessionManager(
            deps=self._deps, user_id=user_id, client_id=client_id, brand_id=brand_id
        )
        if opening_message:
            return self.process_message(
                manager=manager,
                message=opening_message,
                metadata=metadata,
                clarified_goals=clarified_goals,
                goal_agent=goal_agent,
                intent_agent=intent_agent,
                commerce_agent=commerce_agent,
                explain_agent=explain_agent,
                run_research_fn=run_research_fn,
                score_alignment_fn=score_alignment_fn,
                build_profile_with_llm_fn=build_profile_with_llm_fn,
            )
        if clarified_goals:
            self._ingest_clarified_goals(manager, clarified_goals)
        return self._session_response(manager)

    def continue_message(
        self,
        *,
        session_id: str,
        user_id: str | None,
        client_id: str,
        brand_id: str | None,
        message: str,
        metadata: dict | None,
        clarified_goals: list | None,
        goal_agent: _GoalAgent,
        intent_agent: _IntentAgent,
        commerce_agent: _CommerceAgent,
        explain_agent: _ExplainAgent,
        run_research_fn: Callable[..., dict],
        score_alignment_fn: Callable[[List[str], list], list],
        build_profile_with_llm_fn: Callable[[Any], Any],
    ) -> Dict[str, Any]:
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        manager = SessionManager(
            session_id=session_id,
            user_id=user_id,
            client_id=client_id,
            brand_id=brand_id,
            deps=self._deps,
        )
        return self.process_message(
            manager=manager,
            message=message,
            metadata=metadata,
            clarified_goals=clarified_goals,
            goal_agent=goal_agent,
            intent_agent=intent_agent,
            commerce_agent=commerce_agent,
            explain_agent=explain_agent,
            run_research_fn=run_research_fn,
            score_alignment_fn=score_alignment_fn,
            build_profile_with_llm_fn=build_profile_with_llm_fn,
        )

    def get_snapshot(
        self,
        *,
        session_id: str,
        user_id: str | None,
        client_id: str,
    ) -> Dict[str, Any]:
        if user_id:
            session = self._deps.sessions.get_session(
                session_id=session_id, client_id=client_id
            )
            if (
                not session
                or session.get("user_id") != user_id
                or session.get("client_id") != client_id
            ):
                raise HTTPException(status_code=404, detail="Session not found")
        manager = SessionManager(
            deps=self._deps, session_id=session_id, user_id=user_id, client_id=client_id
        )
        return self._session_response(manager)

    def list_sessions(
        self,
        *,
        user_id: str | None,
        client_id: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        sessions = self._deps.sessions.list_sessions(
            user_id=user_id, limit=limit, client_id=client_id
        )
        payload = []
        for session in sessions:
            recent = self._deps.turns.list_recent_turns(
                session_id=session["id"], limit=1
            )
            last_turn = recent[0] if recent else None
            payload.append(
                {
                    "id": session["id"],
                    "client_id": session.get("client_id"),
                    "created_at": session.get("created_at"),
                    "preview": last_turn.get("content") if last_turn else None,
                    "last_turn_at": last_turn.get("created_at") if last_turn else None,
                }
            )
        return {"sessions": payload}

    def delete_session(
        self,
        *,
        session_id: str,
        user_id: str | None,
        client_id: str,
    ) -> Dict[str, str]:
        if user_id:
            session = self._deps.sessions.get_session(
                session_id=session_id, client_id=client_id
            )
            if not session or session.get("user_id") != user_id:
                raise HTTPException(status_code=404, detail="Session not found")
        self._deps.sessions.delete_session(session_id=session_id)
        return {"status": "deleted"}

    def ingest_goals(
        self,
        *,
        session_id: str,
        user_id: str | None,
        client_id: str,
        brand_id: str | None,
        goals: list,
    ) -> Dict[str, Any]:
        if not goals:
            raise HTTPException(
                status_code=400, detail="At least one goal is required."
            )
        manager = SessionManager(
            session_id=session_id,
            user_id=user_id,
            client_id=client_id,
            brand_id=brand_id,
            deps=self._deps,
        )
        self._ingest_clarified_goals(manager, goals)
        return self._session_response(manager, goals=manager.goal_texts())

    def refresh_research(
        self,
        *,
        session_id: str,
        user_id: str | None,
        client_id: str,
        query: str | None,
        run_research_fn: Callable[..., dict],
        score_alignment_fn: Callable[[List[str], list], list],
    ) -> Dict[str, Any]:
        if user_id:
            session = self._deps.sessions.get_session(
                session_id=session_id, client_id=client_id
            )
            if not session or session.get("user_id") != user_id:
                raise HTTPException(status_code=404, detail="Session not found")

        manager = SessionManager(
            deps=self._deps, session_id=session_id, user_id=user_id, client_id=client_id
        )
        query_value = (
            query or manager.get_state().get("last_query") or "product research"
        )
        goals = manager.goal_texts()
        _, context_snapshot = context_for(manager)
        research = self._run_research_compat(
            run_research_fn,
            query=query_value,
            goals=goals,
            context=context_snapshot,
            manager=manager,
        )
        research_stream = self._build_research_stream(
            research, goals, score_alignment_fn=score_alignment_fn
        )
        self._persist_research(manager, research_stream, query=query_value)
        return {
            "query": query_value,
            "goals": goals,
            "research_results": research_stream.get("items") if research_stream else [],
            "updated_at": manager.get_state().get("last_research_at"),
        }

    def process_message(
        self,
        *,
        manager: SessionManager,
        message: str,
        metadata: dict | None,
        clarified_goals: list | None,
        goal_agent: _GoalAgent,
        intent_agent: _IntentAgent,
        commerce_agent: _CommerceAgent,
        explain_agent: _ExplainAgent,
        run_research_fn: Callable[..., dict],
        score_alignment_fn: Callable[[List[str], list], list],
        build_profile_with_llm_fn: Callable[[Any], Any],
    ) -> Dict[str, Any]:
        if clarified_goals:
            self._ingest_clarified_goals(manager, clarified_goals)

        manager.record_turn("user", message, metadata=metadata or {})

        lab_response = self._handle_lab_operator(
            manager=manager,
            message=message,
            metadata=metadata or {},
        )
        if lab_response:
            manager.record_turn(
                "agent",
                lab_response["message"],
                metadata={"type": "lab_operator", "payload": lab_response},
            )
            return self._session_response(
                manager,
                lab_operator=lab_response,
            )

        clarification_state, clarification_reply = self._handle_goal_dialogue(
            manager=manager,
            message=message,
            metadata=metadata,
            goal_agent=goal_agent,
        )
        if clarification_reply:
            return self._session_response(
                manager,
                clarification=clarification_reply,
                goal_state=clarification_state.to_dict()
                if clarification_state
                else None,
            )

        intent = intent_agent.detect_intent(message, manager=manager)
        manager.ingest_intent_as_goal(intent)
        goals = manager.goal_texts()
        intent_signal = intent.get("primary_goal") or intent.get("label") or ""
        if intent_signal:
            manager.record_turn(
                "agent",
                f"Intent inferred: {intent_signal}",
                metadata={
                    "type": "intent_inference",
                    "confidence": intent.get("confidence"),
                },
            )

        _, context_snapshot = context_for(manager)
        plan = commerce_agent.build_plan(
            intent,
            goals=goals,
            context=context_snapshot,
            client_id=manager.client_id,
            brand_id=getattr(manager, "brand_id", None),
        )
        product_explanations = plan.get("product_explanations")
        if not product_explanations:
            product_explanations = self._format_reasoning(plan.get("products", []))
        clarifications = plan.get("clarifications", [])
        explanation = explain_agent.explain(plan.get("products", []))
        manager.record_turn(
            "agent",
            explanation,
            metadata={"type": "plan_explanation", "clarifications": clarifications},
        )
        manager.record_recommendation(
            product_ids=[product["id"] for product in plan.get("products", [])],
            alignment_score=(
                plan.get("alignment", {}).get("goal_alignment", {}) or {}
            ).get("score"),
            context={
                "query": plan.get("query"),
                "goal_alignment": plan.get("alignment", {}).get("goal_alignment"),
                "data_quality": plan.get("data_quality"),
            },
        )
        manager.update_state(
            last_intent=intent,
            last_query=plan.get("query"),
            last_alignment=plan.get("alignment"),
            last_products=plan.get("products") or [],
            last_product_id=(plan.get("products") or [{}])[0].get("id"),
        )

        goal_signals = extract_intent_goals(intent, explicit_goals=goals)
        research = self._run_research_compat(
            run_research_fn,
            query=plan.get("query") or "product research",
            goals=goals,
            context=context_snapshot,
            manager=manager,
        )
        research_stream = self._build_research_stream(
            research, goal_signals, score_alignment_fn=score_alignment_fn
        )
        self._persist_research(
            manager, research_stream, query=plan.get("query") or message
        )

        return self._session_response(
            manager,
            intent=intent,
            plan=self._merge_plan_streams(plan, research_stream),
            research=research,
            baseline_alignment=plan.get("alignment", {})
            .get("goal_alignment", {})
            .get("baseline_score")
            or 0.0,
            intentionality_profiles=self._intentionality_profiles(
                plan.get("products") or [],
                build_profile_with_llm_fn=build_profile_with_llm_fn,
            ),
            explanation=explanation,
            product_explanations=product_explanations,
            goal_state=clarification_state.to_dict()
            if clarification_state
            else manager.get_state().get("clarification_state"),
        )

    def _handle_lab_operator(
        self,
        *,
        manager: SessionManager,
        message: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        text = (message or "").strip().lower()
        if not text:
            return None

        if text.startswith("/lab next") or "run next test" in text:
            experiment_id = metadata.get("experiment_id")
            if not experiment_id:
                experiments = self._deps.experiments.list_experiments(
                    client_id=manager.client_id,
                    product_id=metadata.get("product_id"),
                    brand_id=metadata.get("brand_id") or manager.brand_id,
                    limit=1,
                )
                experiment_id = experiments[0]["id"] if experiments else None
            if not experiment_id:
                return {
                    "action": "run_next_test",
                    "message": "No experiment found to run next test.",
                }

            recommendation = self._orchestrator.suggest_next_test(
                experiment_id=experiment_id, client_id=manager.client_id
            )
            if recommendation.action == "run_variant" and recommendation.variant_id:
                result = self._experiment_runner.run_experiment(
                    experiment_id=experiment_id,
                    variant_id=recommendation.variant_id,
                    client_id=manager.client_id,
                    user_id=manager.user_id,
                )
                return {
                    "action": "run_next_test",
                    "experiment_id": experiment_id,
                    "variant_id": recommendation.variant_id,
                    "metrics": result.metrics,
                    "message": f"Ran next test: {recommendation.reason}",
                }
            if recommendation.action == "create_variant":
                return {
                    "action": "recommend_variant",
                    "experiment_id": experiment_id,
                    "recommendation": recommendation.to_dict(),
                    "message": recommendation.reason,
                }
            return {
                "action": "recommendation",
                "experiment_id": experiment_id,
                "recommendation": recommendation.to_dict(),
                "message": recommendation.reason,
            }

        if text.startswith("/lab why") or "why did" in text and "variant" in text:
            experiment_id = metadata.get("experiment_id")
            variant_id = metadata.get("variant_id")
            variant_label = metadata.get("variant_label")
            if not experiment_id:
                return {
                    "action": "explain_variant",
                    "message": "Provide an experiment_id to explain a variant.",
                }
            if not variant_id and variant_label:
                variants = self._deps.experiments.list_variants(
                    experiment_id=experiment_id
                )
                match = next(
                    (v for v in variants if v.get("label") == variant_label), None
                )
                variant_id = match.get("id") if match else None
            metrics = self._deps.experiment_runs.list_metrics(
                experiment_id=experiment_id, variant_id=variant_id, limit=10
            )
            if not metrics:
                return {
                    "action": "explain_variant",
                    "message": "No metrics found for that variant yet.",
                }
            latest_metric = metrics[0].get("metrics") or {}
            if not variant_id:
                best = max(
                    metrics,
                    key=lambda m: (m.get("metrics") or {}).get("win_rate") or 0,
                )
                variant_id = best.get("variant_id")
                latest_metric = best.get("metrics") or latest_metric

            belief_summary = None
            evidence_payload = None
            brand_id = metadata.get("brand_id") or manager.brand_id
            if brand_id:
                beliefs = self._deps.brand_beliefs.list_beliefs(
                    client_id=manager.client_id,
                    brand_id=brand_id,
                    limit=10,
                )
                for belief in beliefs:
                    evidence = belief.get("evidence") or {}
                    if (
                        evidence.get("experiment_id") == experiment_id
                        and evidence.get("variant_id") == variant_id
                    ):
                        belief_summary = belief.get("metadata", {}).get(
                            "summary"
                        ) or belief.get("recommendation")
                        evidence_payload = evidence
                        break

            detail_parts = [
                f"win rate {latest_metric.get('win_rate')}",
                f"avg score {latest_metric.get('avg_score')}",
            ]
            if evidence_payload:
                query_count = evidence_payload.get("query_count")
                if query_count:
                    detail_parts.append(f"{query_count} queries")
            message = "Latest results: " + " · ".join(detail_parts)
            if belief_summary:
                message += f". Belief: {belief_summary}"
            return {
                "action": "explain_variant",
                "experiment_id": experiment_id,
                "variant_id": variant_id,
                "metrics": latest_metric,
                "evidence": evidence_payload,
                "belief_summary": belief_summary,
                "message": message,
            }

        if text.startswith("/lab what") or "what if" in text:
            prompt = text.lower()
            variant_payload: Dict[str, Any] = {}
            rationale = "Test a targeted change to improve alignment."
            if "price" in prompt or "pricing" in prompt or "discount" in prompt:
                variant_payload = {
                    "pricing": {
                        "strategy": "decrease",
                        "note": "Apply a sharper price signal",
                    }
                }
                rationale = "Test whether sharper pricing improves intent match."
            elif "shipping" in prompt or "delivery" in prompt:
                variant_payload = {
                    "fulfillment": {
                        "speed": "faster",
                        "note": "Highlight faster delivery options",
                    }
                }
                rationale = "Test whether faster delivery improves conversion intent."
            elif "tone" in prompt or "voice" in prompt:
                variant_payload = {
                    "copy": {
                        "tone": "premium",
                        "note": "Shift to a clearer premium tone",
                    }
                }
                rationale = "Test whether tone changes lift perceived fit."
            elif "feature" in prompt or "benefit" in prompt:
                variant_payload = {
                    "copy": {
                        "emphasis": "outcomes",
                        "note": "Emphasize human outcomes first",
                    }
                }
                rationale = "Test whether outcome framing lifts relevance."
            hypothesis = {
                "metric": "win_rate",
                "direction": "increase",
                "rationale": rationale,
                "variant_payload": variant_payload,
            }
            return {
                "action": "what_if_hypothesis",
                "hypothesis": hypothesis,
                "variant_payload": variant_payload,
                "message": "Drafted a what‑if hypothesis and variant payload.",
            }

        if text.startswith("/lab belief") or "create hypothesis from belief" in text:
            brand_id = metadata.get("brand_id") or manager.brand_id
            if not brand_id:
                return {
                    "action": "belief_to_hypothesis",
                    "message": "Select a brand to derive hypothesis from belief.",
                }
            belief = self._deps.brand_beliefs.latest_belief(
                client_id=manager.client_id, brand_id=brand_id
            )
            if not belief:
                return {
                    "action": "belief_to_hypothesis",
                    "message": "No beliefs recorded yet for this brand.",
                }
            hypothesis = {
                "metric": belief.get("metadata", {}).get("metric") or "win_rate",
                "direction": belief.get("metadata", {}).get("direction") or "increase",
                "rationale": belief.get("metadata", {}).get("summary")
                or belief.get("recommendation")
                or "",
                "belief_id": belief.get("id"),
            }
            return {
                "action": "belief_to_hypothesis",
                "hypothesis": hypothesis,
                "message": "Drafted hypothesis from latest belief.",
            }

        return None

    def _session_response(
        self, manager: SessionManager, **payload: Any
    ) -> Dict[str, Any]:
        snapshot = asdict(manager.summary())
        response: Dict[str, Any] = {
            "session_id": manager.session_id,
            "user_id": manager.user_id,
            "snapshot": snapshot,
        }
        response.update(payload)
        return response

    def _handle_goal_dialogue(
        self,
        *,
        manager: SessionManager,
        message: str,
        metadata: Optional[Dict[str, Any]],
        goal_agent: _GoalAgent,
    ):
        state_payload = manager.get_state().get("clarification_state")
        state = (
            manager.clarification_state_from_payload(state_payload)
            if hasattr(manager, "clarification_state_from_payload")
            else None
        )
        if state_payload and state is None:
            # Fallback to GoalClarificationState.from_dict without importing it in application layer.
            try:
                from domain.values.types import GoalClarificationState

                state = GoalClarificationState.from_dict(state_payload)
            except Exception:
                state = None

        if (
            state
            and getattr(state, "ready_for_products", False)
            and getattr(state, "metadata", {}).get("summary_sent")
        ):
            return state, None

        if state:
            state = goal_agent.continue_dialogue(state, message)
        else:
            state = goal_agent.start(message, metadata or {})

        manager.update_state(clarification_state=state.to_dict())
        latest_turn = state.turns[-1] if state.turns else None
        if latest_turn and latest_turn.speaker == "agent":
            manager.record_turn(
                "agent", latest_turn.content, metadata={"type": "clarification"}
            )
            if state.ready_for_products:
                for goal in state.extracted_goals:
                    try:
                        manager.record_goal(goal)
                    except ValueError:
                        continue
                state.metadata["summary_sent"] = True
                manager.update_state(clarification_state=state.to_dict())
            return state, latest_turn.content

        if state.ready_for_products:
            for goal in state.extracted_goals:
                try:
                    manager.record_goal(goal)
                except ValueError:
                    continue
        return state, None

    def _format_reasoning(self, products: List[dict]) -> List[dict]:
        explanations: List[dict] = []
        for product in products or []:
            explanations.append(
                {
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "reasoning": product.get("reasoning", ""),
                    "capabilities_enabled": product.get("capabilities_enabled", []),
                    "confidence": product.get("confidence"),
                }
            )
        return explanations

    def _intentionality_profiles(
        self, products: List[object], *, build_profile_with_llm_fn: Callable[[Any], Any]
    ) -> List[dict]:
        from domain.commerce.types import Product
        from domain.intentionality.types import IntentionalityProfile

        profiles: List[dict] = []
        for product in products or []:
            if isinstance(product, Product):
                profiles.append(build_profile_with_llm_fn(product).to_dict())
                continue
            if isinstance(product, dict):
                profile = product.get("intentionality_profile")
                if profile:
                    profiles.append(profile)
                    continue
                capabilities = list(product.get("capabilities_enabled") or [])
                profile = IntentionalityProfile(
                    product_id=str(product.get("id") or ""),
                    capabilities_enabled=capabilities,
                    goals_served=list(dict.fromkeys(capabilities)),
                    prerequisites=[],
                    outcomes_expected=[],
                    context_fit={},
                )
                profiles.append(profile.to_dict())
                continue
        return profiles

    def _merge_plan_streams(self, plan: dict, research_stream: dict | None) -> dict:
        merged = dict(plan)
        merged["research_results"] = (
            research_stream.get("items") if research_stream else []
        )
        merged["alignment"] = merged.get("alignment") or {}
        merged["alignment"]["research"] = (
            research_stream.get("alignment") if research_stream else {}
        )
        return merged

    def _persist_research(
        self, manager: SessionManager, research_stream: dict | None, *, query: str
    ) -> None:
        if not research_stream:
            return
        manager.update_state(
            last_research=research_stream,
            last_research_query=query,
            last_research_at=datetime.now(timezone.utc).isoformat(),
        )

    def _run_research_compat(
        self,
        run_research_fn: Callable[..., dict],
        *,
        query: str,
        goals: List[str],
        context: str | None,
        manager: SessionManager,
    ) -> dict | None:
        try:
            return run_research_fn(
                query=query,
                goals=goals,
                context=context,
                client_id=manager.client_id,
                user_id=manager.user_id,
                session_id=manager.session_id,
            )
        except TypeError:
            return run_research_fn(query=query, goals=goals, context=context)

    def _build_research_stream(
        self,
        research: dict | None,
        goals: List[str],
        *,
        score_alignment_fn: Callable[[List[str], list], list],
    ) -> dict | None:
        if not research:
            return None
        insights = research.get("insights", []) or []
        if not insights:
            return {
                "items": [],
                "alignment": {"per_item": []},
                "meta": {
                    "confidence": research.get("confidence"),
                    "replay": research.get("replay"),
                },
            }

        from domain.commerce.types import Product

        items = []
        for insight in insights:
            title = insight.get("title") or insight.get("summary") or "Research insight"
            summary = insight.get("summary") or title
            items.append(
                {
                    "id": insight.get("id") or title,
                    "name": title,
                    "price": 0.0,
                    "description": summary,
                    "confidence": insight.get("confidence", 0.35),
                    "source": "research",
                    "offer_url": insight.get("url") or insight.get("source_url"),
                    "capabilities_enabled": [],
                    "tags": ["research"],
                }
            )

        products = [Product(**item) for item in items]
        scores = score_alignment_fn(goals, products) if goals else []
        per_item = {score.product_id: score.__dict__ for score in scores}
        enriched = []
        for item in items:
            score = per_item.get(item["id"], {})
            enriched.append(
                {
                    **item,
                    "alignment_score": score.get("score"),
                    "alignment_reasoning": score.get("alignment_reasoning"),
                }
            )
        return {
            "items": enriched,
            "alignment": {"per_item": list(per_item.values())},
            "meta": {
                "confidence": research.get("confidence"),
                "replay": research.get("replay"),
            },
        }

    def _ingest_clarified_goals(
        self, manager: SessionManager, clarified_goals: list
    ) -> None:
        for clarified_goal in clarified_goals:
            if isinstance(clarified_goal, dict):
                goal_text = clarified_goal.get("goal_text")
                domain = clarified_goal.get("domain")
                importance = clarified_goal.get("importance")
            else:
                goal_text = getattr(clarified_goal, "goal_text", None)
                domain = getattr(clarified_goal, "domain", None)
                importance = getattr(clarified_goal, "importance", None)
            if goal_text:
                manager.record_goal(
                    goal_text, domain=domain, importance=importance or 0.7
                )


__all__ = ["ConversationService"]
