from domain.workflow.approval import ApprovalAuthority, PrincipalType


def approval_authority() -> ApprovalAuthority:
    return ApprovalAuthority(
        principal_type=PrincipalType.HUMAN,
        principal_id="human:operator-a",
        authority_source="verified-test-claims",
        authority_version="v1",
    )


def matching_validation_job(
    deps,
    action,
    *,
    entity_id: str | None = None,
    bind_effect: bool = True,
    status: str = "completed",
    with_result: bool = True,
    model_override: str | None = None,
):
    inputs = action["inputs"]
    execution = None
    if bind_effect:
        execution = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id="client-a",
            workflow_id=action["agent_run_id"],
            action_id=action["id"],
        )
        assert execution is not None
    job = deps.validation_jobs.create_job(
        client_id="client-a",
        brand_id=None,
        product_id=None,
        entity_type="experiment_run",
        entity_id=entity_id or inputs["experiment_id"],
        provider=inputs["provider"],
        mode=inputs["mode"],
        model=model_override or inputs.get("model"),
        prompt_version=inputs["prompt_version"],
        status=status,
        integration_type=None,
        provider_run_id=None,
        callback_verified=False,
        agent_action_id=execution["action_id"] if execution else None,
        approval_id=execution["approval_id"] if execution else None,
        effect_idempotency_key=(
            execution["effect_idempotency_key"] if execution else None
        ),
        approval_effect_execution_id=(execution["execution_id"] if execution else None),
        input_payload={"source": "reconciliation-test"},
        requested_by="operator-a",
    )
    if with_result:
        deps.validation_results.create_result(
            job_id=job["id"],
            provider=job["provider"],
            model=job["requested_model"],
            structured_result={"winner_id": "variant-a", "score": 0.9},
            raw_response=None,
            score=0.9,
            winner_id="variant-a",
            evidence_strength="strong",
            latency_ms=10,
            cost_usd=None,
            source="synthetic",
            callback_verified=False,
        )
    return job
