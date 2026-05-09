from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.composition import default_deps
from api.routes.external_agent_jobs import (
    _decode_external_agent_job_receipt_signature,
    _job_status_payload,
    _sync_job_status_from_run,
)
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from infrastructure.db.agent.external_agent_jobs import (
    get_external_agent_job_by_run_id,
    list_external_agent_job_receipts,
)

router = APIRouter(prefix="/external-agent/jobs/operator", tags=["external-agent-jobs"])


def _deps() -> AppDeps:
    return default_deps()


class ExternalAgentJobOperatorDetailResponse(BaseModel):
    job: Dict[str, Any]
    run: Dict[str, Any]
    receipts: List[Dict[str, Any]]
    latest_receipt: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None


@router.get("/by-run/{run_id}")
def get_external_agent_job_for_operator_route(
    run_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    receipt_limit: int = 20,
    deps: AppDeps = Depends(_deps),
) -> ExternalAgentJobOperatorDetailResponse:
    scoped_client_id = _require_operator_client_id(client_id=client_id, user_id=user_id)
    job, run = _require_operator_scoped_job_and_run(
        deps=deps, run_id=run_id, client_id=scoped_client_id
    )
    receipts = _list_operator_receipts(
        job=job, client_id=scoped_client_id, limit=receipt_limit
    )
    latest_receipt = receipts[0] if receipts else None
    verification = (
        _verify_receipt_for_job(receipt=latest_receipt, job=job, client_id=scoped_client_id)
        if latest_receipt
        else None
    )
    return ExternalAgentJobOperatorDetailResponse(
        job=_job_status_payload(job=job, run=run),
        run=run,
        receipts=receipts,
        latest_receipt=latest_receipt,
        verification=verification,
    )


@router.post("/by-run/{run_id}/receipt/verify")
def verify_external_agent_job_receipt_for_operator_route(
    run_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = _require_operator_client_id(client_id=client_id, user_id=user_id)
    job, _run = _require_operator_scoped_job_and_run(
        deps=deps, run_id=run_id, client_id=scoped_client_id
    )
    receipts = _list_operator_receipts(job=job, client_id=scoped_client_id, limit=1)
    if not receipts:
        raise HTTPException(status_code=404, detail="External agent job receipt not found")
    return _verify_receipt_for_job(
        receipt=receipts[0], job=job, client_id=scoped_client_id
    )


def _require_operator_client_id(*, client_id: str | None, user_id: str | None) -> str:
    if not user_id:
        raise HTTPException(status_code=401, detail="Operator user context is required")
    return require_client_id(client_id, user_id)


def _require_operator_scoped_job_and_run(
    *, deps: AppDeps, run_id: str, client_id: str
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    if str(run.get("principal_type") or "").strip() != "external_agent":
        raise HTTPException(status_code=404, detail="External agent job not found for run")
    job = get_external_agent_job_by_run_id(client_id=client_id, run_id=run_id)
    if not job:
        raise HTTPException(status_code=404, detail="External agent job not found for run")
    job = _sync_job_status_from_run(job=job, run=run)
    return job, run


def _list_operator_receipts(
    *, job: Dict[str, Any], client_id: str, limit: int
) -> List[Dict[str, Any]]:
    rows = list_external_agent_job_receipts(
        job_id=job["id"],
        client_id=client_id,
        principal_id=job["principal_id"],
        limit=limit,
    )
    return sorted(
        [
            {
                **(row.get("payload") or {}),
                "signature": row.get("signature"),
                "signature_algorithm": row.get("signature_algorithm"),
            }
            for row in rows
        ],
        key=lambda item: str(item.get("issued_at") or item.get("created_at") or ""),
        reverse=True,
    )


def _verify_receipt_for_job(
    *, receipt: Dict[str, Any] | None, job: Dict[str, Any], client_id: str
) -> Dict[str, Any]:
    receipt = dict(receipt or {})
    decoded_payload, valid_signature = _decode_external_agent_job_receipt_signature(
        str(receipt.get("signature") or "")
    )
    unsigned_receipt = {
        key: value
        for key, value in receipt.items()
        if key not in {"signature", "signature_algorithm"}
    }
    valid_payload = bool(valid_signature and decoded_payload == unsigned_receipt)
    valid_scope = bool(
        decoded_payload.get("job_id") == job["id"]
        and decoded_payload.get("run_id") == job["run_id"]
        and decoded_payload.get("client_id") == client_id
        and decoded_payload.get("principal_id") == job["principal_id"]
    )
    blockers: List[str] = []
    if not valid_signature:
        blockers.append("Receipt signature is invalid.")
    if valid_signature and not valid_payload:
        blockers.append("Receipt payload does not match the signed payload.")
    if valid_signature and not valid_scope:
        blockers.append("Receipt does not belong to the scoped external-agent job.")
    return {
        "valid": not blockers,
        "valid_signature": valid_signature,
        "valid_payload": valid_payload,
        "valid_scope": valid_scope,
        "key_id": decoded_payload.get("key_id") or receipt.get("key_id"),
        "signature_algorithm": receipt.get("signature_algorithm"),
        "receipt_payload": decoded_payload,
        "blockers": blockers,
    }
