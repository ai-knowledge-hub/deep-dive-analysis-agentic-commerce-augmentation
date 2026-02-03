"""API composition root.

This module wires concrete infrastructure implementations into application
services via `AppDeps`.

Why `api/`?
- `application/` must not import infrastructure (Clean Architecture)
- `infrastructure/` must not import application (adapter direction)
- The outermost layer (API) is allowed to depend on both
"""

from __future__ import annotations

from pathlib import Path

from application.ports.deps import AppDeps
from infrastructure.alignment import goal_alignment_gateway
from infrastructure.db import (
    clients as clients_repo,
    episodes as episodes_repo,
    experiments as experiments_repo,
    experiment_runs as experiment_runs_repo,
    experiment_recommendations as experiment_recommendations_repo,
    experiment_validations as experiment_validations_repo,
    experiment_calibrations as experiment_calibrations_repo,
    analytics_events as analytics_events_repo,
    brand_beliefs as brand_beliefs_repo,
    goals as goals_repo,
    skills as skills_repo,
    platform_profiles as platform_profiles_repo,
    query_batteries as query_batteries_repo,
    replays as replays_repo,
    recommendations as recommendations_repo,
    sessions as sessions_repo,
    simulation_runs as simulation_runs_repo,
    turns as turns_repo,
    users as users_repo,
)
from infrastructure.db.connection import init_db, set_database_path
from infrastructure.db.semantic import DEFAULT_CLIENT_ID, DEFAULT_USER_ID
from infrastructure.llm.gateway import embed, embedding_available, generate
from infrastructure.llm.intent_classifier import classify_intent
from infrastructure.llm.prompts import build_optimization_prompt
from infrastructure.llm.research_agent import run_research
from infrastructure.memory.semantic_memory import SemanticMemory
from infrastructure.simulation.gap_analysis import analyze_gap, derive_lessons
from infrastructure.protocol.acp import discover_acp_candidates, validate_acp_candidate
from infrastructure.protocol.ucp import discover_ucp_candidates, validate_ucp_candidate


def default_deps() -> AppDeps:
    return AppDeps(
        init_db=init_db,
        set_database_path=lambda p: set_database_path(Path(p)),
        sessions=sessions_repo,
        turns=turns_repo,
        goals=goals_repo,
        episodes=episodes_repo,
        recommendations=recommendations_repo,
        users=users_repo,
        replays=replays_repo,
        simulation_runs=simulation_runs_repo,
        clients=clients_repo,
        platform_profiles=platform_profiles_repo,
        query_batteries=query_batteries_repo,
        experiments=experiments_repo,
        experiment_runs=experiment_runs_repo,
        experiment_recommendations=experiment_recommendations_repo,
        experiment_validations=experiment_validations_repo,
        experiment_calibrations=experiment_calibrations_repo,
        analytics_events=analytics_events_repo,
        brand_beliefs=brand_beliefs_repo,
        skills=skills_repo,
        semantic_memory_factory=lambda user_id, client_id: SemanticMemory(
            user_id=user_id, client_id=client_id
        ),
        default_user_id=DEFAULT_USER_ID,
        default_client_id=DEFAULT_CLIENT_ID,
        embedding_available=embedding_available,
        embed=embed,
        generate=generate,
        generate_with_provider=lambda prompt, provider=None, system_instruction=None: generate(
            prompt, system_instruction=system_instruction, provider=provider
        ),
        build_optimization_prompt=build_optimization_prompt,
        run_research=run_research,
        classify_intent=classify_intent,
        alignment_assess=goal_alignment_gateway.assess,
        alignment_score_products=goal_alignment_gateway.score_products,
        simulation_analyze_gap=analyze_gap,
        simulation_derive_lessons=derive_lessons,
        protocol_discover_acp=discover_acp_candidates,
        protocol_discover_ucp=discover_ucp_candidates,
        protocol_validate_acp=validate_acp_candidate,
        protocol_validate_ucp=validate_ucp_candidate,
    )


__all__ = ["default_deps"]
