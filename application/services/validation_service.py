from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException

from application.ports.deps import AppDeps
from application.services.validation.providers import OpenAIMcpAdapter
from application.services.loop.belief_update_service import BeliefUpdateService
from application.services.loop.policy_service import PolicyService
from application.services.loop.state_service import StateService
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
        self._openai_mcp = OpenAIMcpAdapter(settings=get_settings())

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
        agent_action_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        effect_idempotency_key: Optional[str] = None,
        approval_effect_execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_mode = _normalize_validation_mode(mode)
        if normalized_mode is None:
            raise HTTPException(status_code=400, detail="Unsupported validation mode")
        normalized_provider = _normalize_provider(provider)
        if normalized_mode == "provider_openai_mcp" and normalized_provider != "openai":
            raise HTTPException(
                status_code=400,
                detail="provider_openai_mcp mode requires provider=openai",
            )
        if (
            normalized_mode == "provider_gemini_function"
            and normalized_provider != "gemini"
        ):
            raise HTTPException(
                status_code=400,
                detail="provider_gemini_function mode requires provider=gemini",
            )
        initial_status = _initial_job_status(normalized_mode)
        job = self._deps.validation_jobs.create_job(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            entity_type=entity_type,
            entity_id=entity_id,
            provider=normalized_provider,
            mode=normalized_mode,
            model=model,
            prompt_version=prompt_version,
            status=initial_status,
            integration_type=_integration_type_for_mode(normalized_mode),
            provider_run_id=None,
            callback_verified=False,
            agent_action_id=agent_action_id,
            approval_id=approval_id,
            effect_idempotency_key=effect_idempotency_key,
            approval_effect_execution_id=approval_effect_execution_id,
            input_payload=input_payload,
            requested_by=requested_by,
        )
        if normalized_mode == "manual_fallback":
            prompt = build_validation_prompt(
                input_payload=input_payload, schema=VALIDATION_OUTPUT_SCHEMA
            )
            job["external_instructions"] = prompt
            job["external_payload_template"] = VALIDATION_OUTPUT_SCHEMA
        return job

    def start_provider_run(
        self,
        *,
        job_id: str,
        client_id: str,
        callback_url: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id, client_id=client_id)
        if not job:
            raise HTTPException(status_code=404, detail="Validation job not found")
        mode = _normalize_validation_mode(job.get("mode"))
        if mode not in {"provider_openai_mcp", "provider_gemini_function"}:
            raise HTTPException(
                status_code=400,
                detail="Job mode does not support provider run orchestration",
            )
        if mode == "provider_gemini_function":
            raise HTTPException(
                status_code=501,
                detail="Gemini provider-run adapter is not implemented yet",
            )
        if str(job.get("status") or "").lower() in {"completed", "failed"}:
            raise HTTPException(
                status_code=409,
                detail="Cannot start provider run for terminal validation job status",
            )
        _ensure_provider_integrations_enabled(mode=mode)
        provider_run_id = str(uuid.uuid4())
        callback_url_resolved = callback_url or _default_provider_callback_url(
            job_id=job_id
        )
        callback_token = _build_provider_callback_token(
            job_id=job_id,
            client_id=str(job.get("client_id") or ""),
            mode=mode,
            provider_run_id=provider_run_id,
        )
        updated = self._deps.validation_jobs.update_job_status(
            job_id=job_id,
            client_id=client_id,
            status="awaiting_provider_run",
            provider_run_id=provider_run_id,
            callback_verified=False,
        )
        updated_job = updated or job
        launch = self._build_provider_launch(
            mode=mode,
            job=updated_job,
            job_id=job_id,
            provider_run_id=provider_run_id,
            callback_url=callback_url_resolved,
            callback_token=callback_token,
            return_url=return_url,
        )
        return {
            "job": updated_job,
            "provider_run_id": provider_run_id,
            "launch_url": launch["launch_url"],
            "setup_url": launch.get("setup_url"),
            "setup_required": launch.get("setup_required"),
            "instructions": launch.get("instructions"),
            "callback_url": callback_url_resolved,
            "callback_token": callback_token,
            "status": "awaiting_provider_run",
        }

    def submit_provider_result(
        self,
        *,
        job_id: str,
        structured_result: Dict[str, Any],
        raw_response: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        provider_run_id: Optional[str] = None,
        callback_verified: bool = False,
        callback_signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Validation job not found")
        mode = _normalize_validation_mode(job.get("mode"))
        if mode not in {"provider_openai_mcp", "provider_gemini_function"}:
            raise HTTPException(
                status_code=400,
                detail="Job mode does not support provider callback ingestion",
            )
        if mode == "provider_gemini_function":
            raise HTTPException(
                status_code=501,
                detail="Gemini provider-run adapter is not implemented yet",
            )
        if str(job.get("status") or "").lower() == "completed":
            raise HTTPException(
                status_code=409,
                detail="Validation job already completed (possible replay)",
            )
        _ensure_provider_integrations_enabled(mode=mode)
        expected_provider_run_id = str(job.get("provider_run_id") or "")
        if expected_provider_run_id and provider_run_id:
            if provider_run_id != expected_provider_run_id:
                raise HTTPException(status_code=400, detail="provider_run_id mismatch")
        token_to_verify = callback_signature
        if not token_to_verify:
            raise HTTPException(
                status_code=401,
                detail="Missing callback signature/token for provider callback",
            )
        callback_verified = _verify_provider_callback_token(
            token=token_to_verify,
            job_id=job_id,
            client_id=str(job.get("client_id") or ""),
            mode=mode,
            provider_run_id=provider_run_id or expected_provider_run_id,
        )
        if not callback_verified:
            raise HTTPException(
                status_code=401, detail="Invalid callback signature/token"
            )
        token_hash = hashlib.sha256(token_to_verify.encode("utf-8")).hexdigest()
        consumed = self._deps.validation_callback_tokens.consume_token(
            token_hash=token_hash,
            client_id=str(job.get("client_id") or ""),
            job_id=job_id,
            provider_run_id=provider_run_id or expected_provider_run_id,
        )
        if not consumed:
            raise HTTPException(
                status_code=409,
                detail="Callback token has already been used (replay rejected)",
            )
        _validate_structured_result(
            structured_result,
            entity_type=job.get("entity_type"),
            input_payload=job.get("input_payload") or {},
        )
        source = _source_for_provider_mode(mode)
        self._deps.validation_jobs.update_job_status(
            job_id=job_id,
            status="provider_result_received",
            provider_run_id=provider_run_id or expected_provider_run_id or None,
            callback_verified=callback_verified,
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
            source=source,
            callback_verified=callback_verified,
        )
        updated = self._deps.validation_jobs.update_job_status(
            job_id=job_id,
            status="completed",
            model=model or job.get("model"),
            provider_run_id=provider_run_id or job.get("provider_run_id"),
            callback_verified=callback_verified,
        )
        updated_job = updated or job
        self._record_learning_loop(job=updated_job, result=result, source=source)
        return {"job": updated_job, "result": result}

    def run_job(self, *, job_id: str) -> Dict[str, Any]:
        return self.run_job_scoped(job_id=job_id, client_id=None)

    def run_job_scoped(
        self, *, job_id: str, client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id, client_id=client_id)
        if not job:
            raise HTTPException(status_code=404, detail="Validation job not found")
        mode = _normalize_validation_mode(job.get("mode"))
        if mode != "in_app_byok":
            raise HTTPException(status_code=400, detail="Job is external-only")
        self._deps.validation_jobs.update_job_status(
            job_id=job_id, client_id=client_id, status="running"
        )
        provider = _normalize_provider(job.get("provider"))
        requested_model = (
            job.get("requested_model")
            if job.get("approval_effect_execution_id") is not None
            else job.get("requested_model") or job.get("model")
        )
        prompt = build_validation_prompt(
            input_payload=job.get("input_payload") or {},
            schema=VALIDATION_OUTPUT_SCHEMA,
        )
        start = time.perf_counter()
        try:
            response = _run_validation_prompt(
                prompt=prompt, provider=provider, model=requested_model
            )
        except Exception as exc:  # pragma: no cover - provider failures
            self._deps.validation_jobs.update_job_status(
                job_id=job_id, client_id=client_id, status="failed"
            )
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
            model=requested_model,
            structured_result=structured,
            raw_response=response,
            score=_safe_float(structured.get("score")),
            winner_id=_safe_str(structured.get("winner_id")),
            evidence_strength=_safe_str(structured.get("evidence_strength")),
            latency_ms=latency_ms,
            cost_usd=None,
            source="synthetic",
            callback_verified=False,
        )
        self._deps.validation_jobs.update_job_status(
            job_id=job_id, client_id=client_id, status="completed"
        )
        self._record_learning_loop(job=job, result=result, source="synthetic")
        return {"job": job, "result": result}

    def submit_external_result(
        self,
        *,
        job_id: str,
        client_id: Optional[str] = None,
        structured_result: Dict[str, Any],
        raw_response: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id, client_id=client_id)
        if not job:
            raise HTTPException(status_code=404, detail="Validation job not found")
        mode = _normalize_validation_mode(job.get("mode"))
        if mode != "manual_fallback":
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
            source="external_synthetic",
            callback_verified=False,
        )
        self._deps.validation_jobs.update_job_status(
            job_id=job_id,
            client_id=client_id,
            status="completed",
            model=model or job.get("model"),
        )
        self._record_learning_loop(job=job, result=result, source="external_synthetic")
        return {"job": job, "result": result}

    def get_job(
        self, *, job_id: str, client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        job = self._deps.validation_jobs.get_job(job_id=job_id, client_id=client_id)
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

    def _build_provider_launch(
        self,
        *,
        mode: str,
        job: Dict[str, Any],
        job_id: str,
        provider_run_id: str,
        callback_url: Optional[str] = None,
        callback_token: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> Dict[str, object]:
        if mode == "provider_openai_mcp":
            if not callback_url or not callback_token:
                raise HTTPException(
                    status_code=500,
                    detail="Missing callback contract for OpenAI MCP launch",
                )
            return self._openai_mcp.build_launch_contract(
                job_id=job_id,
                provider_run_id=provider_run_id,
                callback_url=callback_url,
                callback_token=callback_token,
                return_url=return_url,
                entity_type=job.get("entity_type"),
                provider=job.get("provider"),
            )
        raise HTTPException(
            status_code=501, detail=f"Unsupported provider mode: {mode}"
        )

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


def _normalize_validation_mode(mode: Optional[str]) -> Optional[str]:
    if not mode:
        return None
    normalized = str(mode).strip().lower()
    legacy_map = {
        "in_app": "in_app_byok",
        "external": "manual_fallback",
    }
    normalized = legacy_map.get(normalized, normalized)
    allowed = {
        "in_app_byok",
        "provider_openai_mcp",
        "provider_gemini_function",
        "manual_fallback",
    }
    return normalized if normalized in allowed else None


def _initial_job_status(mode: str) -> str:
    if mode == "manual_fallback":
        return "awaiting_external"
    if mode in {"provider_openai_mcp", "provider_gemini_function"}:
        return "awaiting_provider_run"
    return "created"


def _integration_type_for_mode(mode: str) -> str:
    if mode == "provider_openai_mcp":
        return "openai_mcp"
    if mode == "provider_gemini_function":
        return "gemini_function"
    if mode == "manual_fallback":
        return "manual_external"
    return "in_app_byok"


def _source_for_provider_mode(mode: str) -> str:
    if mode == "provider_openai_mcp":
        return "provider_openai_mcp"
    if mode == "provider_gemini_function":
        return "provider_gemini_function"
    return "synthetic"


def _ensure_provider_integrations_enabled(*, mode: str) -> None:
    settings = get_settings()
    enabled = bool(settings.enable_provider_validation_integrations)
    if enabled:
        return
    raise HTTPException(
        status_code=501,
        detail=(
            f"Provider-integrated validation mode ({mode}) is not enabled. "
            "Set ENABLE_PROVIDER_VALIDATION_INTEGRATIONS=true to activate."
        ),
    )


def _default_provider_callback_url(*, job_id: str) -> str:
    settings = get_settings()
    base = settings.backend_public_url.rstrip("/")
    return f"{base}/validation/jobs/{job_id}/provider-callback"


def _build_provider_callback_token(
    *,
    job_id: str,
    client_id: str,
    mode: str,
    provider_run_id: str,
) -> str:
    settings = get_settings()
    secret = settings.validation_callback_signing_secret or settings.openai_api_key
    if not secret:
        raise HTTPException(
            status_code=500,
            detail=(
                "Missing validation callback signing secret. "
                "Set VALIDATION_CALLBACK_SIGNING_SECRET."
            ),
        )
    payload = {
        "job_id": job_id,
        "client_id": client_id,
        "mode": mode,
        "provider_run_id": provider_run_id,
        "exp": int(time.time()) + max(1, int(settings.validation_callback_ttl_seconds)),
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def _verify_provider_callback_token(
    *,
    token: str,
    job_id: str,
    client_id: str,
    mode: str,
    provider_run_id: str,
) -> bool:
    try:
        payload_b64, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    settings = get_settings()
    secret = settings.validation_callback_signing_secret or settings.openai_api_key
    if not secret:
        return False
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, signature):
        return False
    try:
        padding = "=" * (-len(payload_b64) % 4)
        payload_raw = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return False
    if int(payload.get("exp") or 0) < int(time.time()):
        return False
    if payload.get("job_id") != job_id:
        return False
    if payload.get("client_id") != client_id:
        return False
    if payload.get("mode") != mode:
        return False
    if payload.get("provider_run_id") != provider_run_id:
        return False
    return True


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
    for field in ("score", "confidence"):
        value = _safe_float(result.get(field))
        if value is None:
            raise HTTPException(
                status_code=400, detail=f"{field} must be a numeric value"
            )
        if not (0.0 <= value <= 1.0):
            raise HTTPException(
                status_code=400, detail=f"{field} must be within [0, 1]"
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
