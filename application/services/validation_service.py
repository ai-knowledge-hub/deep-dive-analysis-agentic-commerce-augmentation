from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException

from application.ports.deps import AppDeps
from application.services.belief_update_service import BeliefUpdateService
from application.services.policy_service import PolicyService
from application.services.state_service import StateService
from shared.llm.prompts import build_validation_prompt, VALIDATION_OUTPUT_SCHEMA
from shared.config.env import get_settings
from shared.llm.clients.openai import OpenAIConfig, OpenAILLMClient
from shared.llm.clients.anthropic import AnthropicConfig, AnthropicLLMClient
from shared.llm.clients.openrouter import OpenRouterConfig, OpenRouterLLMClient
from shared.llm.clients.gemini import GeminiConfig, GeminiLLMClient


class ValidationService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._belief_updates = BeliefUpdateService(deps=deps)
        self._policy = PolicyService(deps=deps)
        self._state = StateService(deps=deps)

    def create_job(
        self,
        *,
        client_id: str,
        entity_type: str,
        entity_id: str,
        provider: str,
        mode: str,
        input_payload: Dict[str, Any],
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        model: Optional[str] = None,
        prompt_version: Optional[str] = "v1",
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        if mode not in {"in_app", "external"}:
            raise HTTPException(status_code=400, detail="Unsupported validation mode")
        job = self._deps.validation_jobs.create_job(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider,
            mode=mode,
            model=model,
            prompt_version=prompt_version,
            status="awaiting_external" if mode == "external" else "created",
            input_payload=input_payload,
            requested_by=requested_by,
        )
        if mode == "external":
            prompt = build_validation_prompt(
                input_payload=input_payload, schema=VALIDATION_OUTPUT_SCHEMA
            )
            job["external_instructions"] = prompt
            job["external_payload_template"] = VALIDATION_OUTPUT_SCHEMA
        return job

    def run_job(self, *, job_id: str) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Validation job not found")
        if job.get("mode") != "in_app":
            raise HTTPException(status_code=400, detail="Job is external-only")
        self._deps.validation_jobs.update_job_status(job_id=job_id, status="running")
        provider = _normalize_provider(job.get("provider"))
        prompt = build_validation_prompt(
            input_payload=job.get("input_payload") or {},
            schema=VALIDATION_OUTPUT_SCHEMA,
        )
        start = time.perf_counter()
        try:
            response = _run_validation_prompt(
                prompt=prompt, provider=provider, model=job.get("model")
            )
        except Exception as exc:  # pragma: no cover - provider failures
            self._deps.validation_jobs.update_job_status(job_id=job_id, status="failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        latency_ms = int((time.perf_counter() - start) * 1000)
        structured = _parse_json_response(response)
        _validate_structured_result(
            structured,
            entity_type=job.get("entity_type"),
            input_payload=job.get("input_payload") or {},
        )
        result = self._deps.validation_results.create_result(
            job_id=job_id,
            provider=job.get("provider"),
            model=job.get("model"),
            structured_result=structured,
            raw_response=response,
            score=_safe_float(structured.get("score")),
            winner_id=_safe_str(structured.get("winner_id")),
            evidence_strength=_safe_str(structured.get("evidence_strength")),
            latency_ms=latency_ms,
            cost_usd=None,
        )
        self._deps.validation_jobs.update_job_status(job_id=job_id, status="completed")
        self._record_learning_loop(job=job, result=result, source="synthetic")
        return {"job": job, "result": result}

    def submit_external_result(
        self,
        *,
        job_id: str,
        structured_result: Dict[str, Any],
        raw_response: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Validation job not found")
        if job.get("mode") != "external":
            raise HTTPException(status_code=400, detail="Job is in-app only")
        _validate_structured_result(
            structured_result,
            entity_type=job.get("entity_type"),
            input_payload=job.get("input_payload") or {},
        )
        result = self._deps.validation_results.create_result(
            job_id=job_id,
            provider=provider or job.get("provider"),
            model=model or job.get("model"),
            structured_result=structured_result,
            raw_response=raw_response,
            score=_safe_float(structured_result.get("score")),
            winner_id=_safe_str(structured_result.get("winner_id")),
            evidence_strength=_safe_str(structured_result.get("evidence_strength")),
            latency_ms=None,
            cost_usd=None,
        )
        self._deps.validation_jobs.update_job_status(
            job_id=job_id, status="completed", model=model or job.get("model")
        )
        self._record_learning_loop(job=job, result=result, source="observed")
        return {"job": job, "result": result}

    def get_job(self, *, job_id: str) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Validation job not found")
        result = self._deps.validation_results.get_latest_for_job(job_id=job_id)
        return {"job": job, "result": result}

    def list_jobs(
        self,
        *,
        client_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        jobs = self._deps.validation_jobs.list_jobs(
            client_id=client_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )
        return {"jobs": jobs}

    def _record_learning_loop(
        self,
        *,
        job: Dict[str, Any],
        result: Dict[str, Any],
        source: str,
    ) -> None:
        client_id = str(job.get("client_id") or "")
        if not client_id:
            return
        brand_id = job.get("brand_id")
        product_id = job.get("product_id")
        structured = result.get("structured_result") or {}
        hypothesis_key = f"validation:{job.get('entity_type')}:{job.get('entity_id')}"
        evidence = {
            "source": source,
            "provider": result.get("provider") or job.get("provider"),
            "model": result.get("model") or job.get("model"),
            "score": structured.get("score", result.get("score", 0.5)),
            "confidence": structured.get("confidence", 0.5),
            "winner_id": structured.get("winner_id", result.get("winner_id")),
            "evidence_strength": structured.get(
                "evidence_strength", result.get("evidence_strength")
            ),
            "validation_job_id": job.get("id"),
            "validation_result_id": result.get("id"),
            "entity_type": job.get("entity_type"),
            "entity_id": job.get("entity_id"),
            "support_size": 1,
        }
        revision = self._belief_updates.update(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            hypothesis_key=hypothesis_key,
            evidence=evidence,
        )
        uncertainty = 1.0 - float(revision.get("confidence", 0.0))
        self._policy.record_decision(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            policy_action="update_belief_only",
            uncertainty=uncertainty,
            expected_gain=float(revision.get("posterior", 0.0)),
            selected_reason="validation_completed",
        )
        self._state.snapshot(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            state={
                "hypothesis_key": hypothesis_key,
                "posterior": revision.get("posterior"),
                "confidence": revision.get("confidence"),
                "source": source,
                "winner_id": evidence.get("winner_id"),
            },
        )


def _normalize_provider(provider: Optional[str]) -> str:
    if not provider:
        return "openrouter"
    value = provider.lower().strip()
    if value == "claude":
        return "anthropic"
    return value


def _parse_json_response(text: str) -> Dict[str, Any]:
    if not text:
        raise HTTPException(status_code=400, detail="Empty model response")
    trimmed = text.strip()
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise HTTPException(status_code=400, detail="Model output is not JSON")
        try:
            return json.loads(trimmed[start : end + 1])
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="Unable to parse JSON output"
            ) from exc


def _validate_structured_result(
    result: Dict[str, Any],
    *,
    entity_type: Optional[str] = None,
    input_payload: Optional[Dict[str, Any]] = None,
) -> None:
    required = ["winner_id", "score", "confidence", "evidence_strength"]
    missing = [key for key in required if key not in result]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}",
        )
    if result.get("evidence_strength") not in {"weak", "moderate", "strong"}:
        raise HTTPException(
            status_code=400, detail="evidence_strength must be weak/moderate/strong"
        )
    if (
        entity_type == "copy_revision"
        or (input_payload or {}).get("type") == "copy_revision"
    ):
        winner = str(result.get("winner_id") or "").strip().lower()
        if winner not in {"control", "candidate"}:
            raise HTTPException(
                status_code=400,
                detail='winner_id must be "control" or "candidate" for copy_revision',
            )


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _run_validation_prompt(
    *, prompt: str, provider: str, model: Optional[str] = None
) -> str:
    settings = get_settings()
    if provider == "openai":
        api_key = settings.openai_validation_api_key or settings.openai_api_key
        model_name = model or settings.openai_validation_model or settings.openai_model
        client = OpenAILLMClient(
            OpenAIConfig(
                api_key=api_key,
                model=model_name or settings.openai_model,
                temperature=float(settings.openai_temperature),
                max_tokens=int(settings.openai_max_tokens),
            )
        )
        return client.generate(prompt)
    if provider == "anthropic":
        api_key = settings.anthropic_validation_api_key or settings.anthropic_api_key
        model_name = (
            model or settings.anthropic_validation_model or settings.anthropic_model
        )
        client = AnthropicLLMClient(
            AnthropicConfig(
                api_key=api_key,
                model=model_name or settings.anthropic_model,
                temperature=float(settings.anthropic_temperature),
                max_tokens=int(settings.anthropic_max_tokens),
            )
        )
        return client.generate(prompt)
    if provider == "gemini":
        api_key = settings.gemini_validation_api_key or settings.gemini_api_key
        primary = model or settings.gemini_validation_model or settings.gemini_model
        priority = [primary] if primary else [settings.gemini_model]
        client = GeminiLLMClient(
            GeminiConfig(
                api_key=api_key,
                model_priority=priority,
            )
        )
        return client.generate(prompt)
    if provider == "openrouter":
        api_key = settings.openrouter_validation_api_key or settings.openrouter_api_key
        model_name = (
            model or settings.openrouter_validation_model or settings.openrouter_model
        )
        client = OpenRouterLLMClient(
            OpenRouterConfig(
                api_key=api_key,
                model=model_name or settings.openrouter_model,
                temperature=float(settings.openrouter_temperature),
                max_tokens=int(settings.openrouter_max_tokens),
                site_url=settings.openrouter_site_url,
                app_name=settings.openrouter_app_name,
            )
        )
        return client.generate(prompt)
    raise HTTPException(status_code=400, detail="Unsupported provider")


__all__ = ["ValidationService"]
