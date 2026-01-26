from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.simulation import repository as _repo


def create_run(
    *,
    query: str,
    scenario: dict,
    products: list,
    result: dict,
    user_id: str | None = None,
    session_id: str | None = None,
    client_id: str,
    brand_id: str | None = None,
    product_id: str | None = None,
) -> Dict[str, Any]:
    return _repo.create_run(
        query=query,
        scenario=scenario,
        products=products,
        result=result,
        user_id=user_id,
        session_id=session_id,
        client_id=client_id,
        brand_id=brand_id,
        product_id=product_id,
    )


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return _repo.get_run(run_id)


def list_runs(
    *,
    client_id: str,
    user_id: str | None = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    return _repo.list_runs(user_id=user_id, limit=limit, client_id=client_id)


def update_retest(run_id: str, retest: dict) -> None:
    _repo.update_retest(run_id, retest)


def update_scenario(run_id: str, scenario: dict) -> None:
    _repo.update_scenario(run_id, scenario)


def update_run_linkage(
    run_id: str,
    *,
    client_id: str,
    product_id: str,
    brand_id: str | None = None,
) -> Optional[Dict[str, Any]]:
    return _repo.update_run_linkage(
        run_id, client_id=client_id, product_id=product_id, brand_id=brand_id
    )


def list_lessons(
    *,
    client_id: str,
    user_id: str | None = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    return _repo.list_lessons(user_id=user_id, limit=limit, client_id=client_id)


__all__ = [
    "create_run",
    "get_run",
    "list_runs",
    "update_retest",
    "update_scenario",
    "update_run_linkage",
    "list_lessons",
]

