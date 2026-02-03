"""Dependency container for application services.

The goal is to keep `application/*` free of imports from `infrastructure/*`.
Concrete implementations are wired in the composition root (API/infrastructure).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


class SessionsStore(Protocol):
    def create_session(
        self,
        *,
        user_id: str | None,
        state: dict | None,
        client_id: str,
        brand_id: str | None = None,
    ) -> dict: ...

    def get_session(
        self, *, session_id: str, client_id: str | None = None
    ) -> dict | None: ...

    def update_state(self, *, session_id: str, state: dict) -> None: ...

    def list_sessions(
        self, *, client_id: str, user_id: str | None = None, limit: int = 20
    ) -> list[dict]: ...

    def delete_session(self, *, session_id: str) -> None: ...


class TurnsStore(Protocol):
    def add_turn(
        self,
        *,
        session_id: str,
        speaker: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict: ...

    def list_turns(self, *, session_id: str, limit: int = 100) -> list[dict]: ...

    def list_recent_turns(self, *, session_id: str, limit: int = 1) -> list[dict]: ...


class GoalsStore(Protocol):
    def create_goal(self, **kwargs: Any) -> dict: ...

    def list_goals_for_session(self, **kwargs: Any) -> list[dict]: ...


class EpisodesStore(Protocol):
    def create_episode(self, **kwargs: Any) -> dict: ...

    def get_latest(self, **kwargs: Any) -> dict | None: ...


class RecommendationsStore(Protocol):
    def create_recommendation(self, **kwargs: Any) -> dict: ...


class UsersStore(Protocol):
    def ensure_user(self, user_id: str) -> None: ...


class ReplaysStore(Protocol):
    def create_replay_record(self, **kwargs: Any) -> dict: ...

    def list_replay_records(self, **kwargs: Any) -> list[dict]: ...

    def get_replay_record(self, replay_id: str, **kwargs: Any) -> dict | None: ...


class SimulationRunsStore(Protocol):
    def create_run(self, **kwargs: Any) -> dict: ...

    def get_run(self, **kwargs: Any) -> dict | None: ...

    def list_runs(self, **kwargs: Any) -> list[dict]: ...

    def list_lessons(self, **kwargs: Any) -> list[dict]: ...

    def update_retest(self, run_id: str, retest: dict) -> None: ...

    def update_scenario(self, run_id: str, scenario: dict) -> None: ...

    def update_run_linkage(self, run_id: str, **kwargs: Any) -> dict | None: ...

    def update_run(self, **kwargs: Any) -> dict | None: ...


class ClientsStore(Protocol):
    def create_client(self, **kwargs: Any) -> dict: ...

    def list_clients(self, **kwargs: Any) -> list[dict]: ...

    def create_brand(self, **kwargs: Any) -> dict: ...

    def list_brands(self, **kwargs: Any) -> list[dict]: ...

    def create_product(self, **kwargs: Any) -> dict: ...

    def list_products(self, **kwargs: Any) -> list[dict]: ...

    def get_brand(self, **kwargs: Any) -> dict | None: ...

    def get_product(self, **kwargs: Any) -> dict | None: ...

    def get_product_for_client(self, **kwargs: Any) -> dict | None: ...

    def add_client_user(self, **kwargs: Any) -> dict: ...

    def list_client_users(self, **kwargs: Any) -> list[dict]: ...

    def search_products_for_client(self, **kwargs: Any) -> list[dict]: ...

    def update_brand_metadata(self, **kwargs: Any) -> dict | None: ...

    def update_product(self, **kwargs: Any) -> dict | None: ...


class PlatformProfilesStore(Protocol):
    def get_platform_profile(self, **kwargs: Any) -> dict | None: ...

    def upsert_platform_profile(self, **kwargs: Any) -> dict: ...

    def ensure_platform_profile(self, **kwargs: Any) -> dict: ...


class QueryBatteriesStore(Protocol):
    def create_battery(self, **kwargs: Any) -> dict: ...

    def get_battery(self, **kwargs: Any) -> dict | None: ...

    def list_batteries(self, **kwargs: Any) -> list[dict]: ...

    def update_battery(self, **kwargs: Any) -> dict | None: ...

    def add_query(self, **kwargs: Any) -> dict: ...

    def get_query(self, **kwargs: Any) -> dict | None: ...

    def list_queries(self, **kwargs: Any) -> list[dict]: ...

    def update_query(self, **kwargs: Any) -> dict | None: ...


class ExperimentsStore(Protocol):
    def create_experiment(self, **kwargs: Any) -> dict: ...

    def get_experiment(self, **kwargs: Any) -> dict | None: ...

    def list_experiments(self, **kwargs: Any) -> list[dict]: ...

    def list_all_experiments(self, **kwargs: Any) -> list[dict]: ...

    def update_experiment(self, **kwargs: Any) -> dict | None: ...

    def add_variant(self, **kwargs: Any) -> dict: ...

    def get_variant(self, **kwargs: Any) -> dict | None: ...

    def list_variants(self, **kwargs: Any) -> list[dict]: ...

    def list_due_experiments(self, **kwargs: Any) -> list[dict]: ...


class ExperimentRunsStore(Protocol):
    def create_run(self, **kwargs: Any) -> dict: ...

    def list_runs(self, **kwargs: Any) -> list[dict]: ...

    def create_metric(self, **kwargs: Any) -> dict: ...

    def list_metrics(self, **kwargs: Any) -> list[dict]: ...


class ExperimentRecommendationsStore(Protocol):
    def create_recommendation(self, **kwargs: Any) -> dict: ...

    def list_recommendations(self, **kwargs: Any) -> list[dict]: ...


class ExperimentValidationsStore(Protocol):
    def create_validation(self, **kwargs: Any) -> dict: ...

    def list_validations(self, **kwargs: Any) -> list[dict]: ...

    def accuracy_summary(self, **kwargs: Any) -> dict: ...

    def count_validations(self, **kwargs: Any) -> int: ...


class ExperimentCalibrationsStore(Protocol):
    def upsert_calibration(self, **kwargs: Any) -> dict: ...

    def get_calibration(self, **kwargs: Any) -> dict | None: ...


class AnalyticsEventsStore(Protocol):
    def create_event(self, **kwargs: Any) -> dict: ...

    def list_events(self, **kwargs: Any) -> list[dict]: ...


class BrandBeliefsStore(Protocol):
    def create_belief(self, **kwargs: Any) -> dict: ...

    def list_beliefs(self, **kwargs: Any) -> list[dict]: ...

    def latest_belief(self, **kwargs: Any) -> dict | None: ...


class SkillsStore(Protocol):
    def get_skill(self, **kwargs: Any) -> dict | None: ...

    def upsert_skill(self, **kwargs: Any) -> dict: ...

    def list_skill_history(self, **kwargs: Any) -> list[dict]: ...


class SemanticMemory(Protocol):
    def get(self, key: str) -> list[str]: ...

    def append(self, key: str, value: str) -> None: ...


@dataclass(frozen=True)
class AppDeps:
    # DB bootstrap (used by tests)
    init_db: Callable[[], None]
    set_database_path: Callable[[Path], None]

    # DB repositories
    sessions: SessionsStore
    turns: TurnsStore
    goals: GoalsStore
    episodes: EpisodesStore
    recommendations: RecommendationsStore
    users: UsersStore
    replays: ReplaysStore
    simulation_runs: SimulationRunsStore
    clients: ClientsStore
    platform_profiles: PlatformProfilesStore
    query_batteries: QueryBatteriesStore
    experiments: ExperimentsStore
    experiment_runs: ExperimentRunsStore
    experiment_recommendations: ExperimentRecommendationsStore
    experiment_validations: ExperimentValidationsStore
    experiment_calibrations: ExperimentCalibrationsStore
    analytics_events: AnalyticsEventsStore
    brand_beliefs: BrandBeliefsStore
    skills: SkillsStore

    # Semantic memory
    semantic_memory_factory: Callable[[str, str], SemanticMemory]
    default_user_id: str
    default_client_id: str

    # Embeddings (optional)
    embedding_available: Callable[[], bool]
    embed: Callable[[str], list[float]]

    # LLM + tools
    generate: Callable[[str], str]
    generate_with_provider: Callable[..., str]
    build_optimization_prompt: Callable[..., str]
    run_research: Callable[..., dict]
    classify_intent: Callable[..., dict]

    # Alignment gateway (semantic + keyword fallback is handled inside gateway)
    alignment_assess: Callable[..., Any]
    alignment_score_products: Callable[..., list]

    # Simulation gap analysis (may use embeddings in infrastructure)
    simulation_analyze_gap: Callable[..., dict]
    simulation_derive_lessons: Callable[..., list]

    # Protocol discovery (Layer 2) adapters
    protocol_discover_acp: Callable[..., list]
    protocol_discover_ucp: Callable[..., list]
    protocol_validate_acp: Callable[..., list]
    protocol_validate_ucp: Callable[..., list]
