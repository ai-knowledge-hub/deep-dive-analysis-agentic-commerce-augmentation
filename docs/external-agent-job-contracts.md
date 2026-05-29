# External Agent Job Contracts

Status: current
Last updated: 2026-05-10

This document defines the machine-facing job contract for external assistants calling the agentic commerce control plane.

The goal is to give external agents a stable, retry-safe API that does not require them to behave like human UI users.

## Contract Principles

- External agents authenticate as `principal_type=external_agent` using signed bearer tokens.
- Every submitted job requires an `idempotency_key`.
- Duplicate submissions with the same principal, tenant, and idempotency key return the same job/run once created; simultaneous duplicate submissions can receive retryable `409` while the first request is still planning.
- Duplicate submissions with a different payload are rejected with `409`.
- Requested skills/tools must be allowed by token scopes.
- Submitted jobs create a linked `agent_run` so the human control plane can inspect, intervene, and audit execution.
- Job status is scoped to the same external principal that created the job.

## Authentication

External jobs require an agent principal bearer token.

Token claims are resolved by `api/utils/principals.py` and must include:

- `principal_type=external_agent`
- `principal_id`
- `client_id`
- `exp` within the configured maximum TTL
- `iat`
- `jti`
- `kid`
- `aud`
- `iss`
- `scopes`

`agent_profile_id` is optional, but when a bearer-authenticated caller wants to create a run under a profile, the profile must be present in the signed token. Request bodies cannot self-assert a profile that is absent from the bearer token.

The persisted principal row must also be active. Setting a principal status to anything other than `active` revokes future bearer-token use for that principal, even when an existing token is otherwise correctly signed.

Required scopes:

- `external_agent_jobs:write` or `agent_runs:write` for job creation.
- `external_agent_jobs:read`, `external_agent_jobs:write`, `agent_runs:read`, or `agent_runs:write` for status reads.
- The same read/write scopes allow receipt and event reads.

Skill/tool scopes:

- Tool request requires `tool:<tool_id>` or `tools:*`.
- Skill request requires `skill:<skill_id>` or `skills:*`.
- Registry discovery via `GET /agent-runs/registry` requires a tenant/user context or a bearer token with `external_agent_jobs:read`, `external_agent_jobs:write`, `agent_runs:read`, or `agent_runs:write`.

Credential metadata:

```http
GET /external-agent/credentials/metadata
```

The metadata endpoint exposes the current token contract for integrators: token type, signing algorithm, current `kid`, expected audience, issuer, default TTL, maximum TTL, and whether server-side key rotation/JWKS-style discovery is available. The current implementation is issuer-managed HMAC with a single configured key id; token issuance and rotation APIs are still future work.

## Discover Runtime Tools

Endpoint:

```http
GET /agent-runs/registry
Authorization: Bearer <agent-principal-token>
```

Use the registry before creating jobs. Executable tools and capabilities include an `external_agent_contract` block with accepted plan modes, required scope alternatives, candidate/default skills, and a minimal request template. Harness profiles include `allowed_effect_classes`; job/run creation rejects requested capabilities whose planned effect class is outside the selected harness boundary, for example write actions under `observe_only`. Harness `planner_mode` also shapes the initial action queue: inspect/recommend harnesses keep read/recommend proposals, while bounded harnesses honor single-tool and max-initial-action constraints. Implemented harness stopping conditions can pause or complete runs at runtime; for example, `external_side_effect_required` pauses before pending external/high-risk actions, `budget_exhausted` pauses when declared action/variant/cost budgets are consumed, `policy_block` pauses when policy blocks an action, `operator_pause` records explicit operator pauses, and `all_actions_decided` completes operator-supervised plans after approval/rejection decisions. `memory_policy=no_mutation` blocks learning/memory mutation capabilities at job/run creation and execution time; callers can inspect `memory_policy_contracts[]`, plus each tool/capability `memory_effect` and `blocked_by_memory_policies`, before requesting work. Skill-only declarations that are not accepted by `POST /external-agent/jobs` are marked through `skill_tool_mappings[].executable=false` and listed in `declared_non_executable_skill_tools`. Protocol checkout, payment, and browser fallback readiness boundaries are also exposed directly in `readiness_boundaries[]` with `tool_id`, `skill_ids`, `adapter_id`, `contract_intent=readiness_boundary`, `blocked_reason`, and the planned receipt contract so callers can distinguish market-research readiness signals from executable transaction tools without reverse-engineering lower-level mappings. The same metadata is mirrored on matching `skill_tool_mappings[]` rows for compatibility.

## Create Job

Endpoint:

```http
POST /external-agent/jobs
Authorization: Bearer <agent-principal-token>
Content-Type: application/json
```

Minimal body:

```json
{
  "idempotency_key": "job-123",
  "tool_id": "experiment.run_variant",
  "objective": {
    "goal": "test one candidate variant"
  }
}
```

Supported body fields:

| Field | Required | Notes |
| --- | --- | --- |
| `idempotency_key` | Yes | Stable caller-generated retry key. |
| `tool_id` | Conditional | Machine-facing runtime tool, for example `experiment.run_variant`. |
| `skill_id` | No | Optional preferred skill. Must be compatible with `tool_id`. |
| `capability_name` | Conditional | Legacy/runtime capability name. Used when `tool_id` is not supplied. |
| `allowed_capabilities` | Conditional | Explicit action queue capabilities. Required if neither `tool_id` nor `capability_name` is supplied. |
| `plan_mode` | No | `single_tool` or `workflow`. Defaults to `single_tool` when `tool_id`/`capability_name` is supplied, otherwise `workflow` for capability-list jobs. |
| `objective` | No | Caller intent/context copied into the linked run objective. |
| `brand_id` | No | Optional tenant-scoped brand anchor. |
| `product_id` | No | Optional tenant-scoped product anchor. |
| `experiment_id` | No | Optional tenant-scoped experiment anchor. |
| `capability_versions` | No | Optional capability version pins. |
| `budgets` | No | Optional run budget metadata. |
| `approval_policy` | No | Optional approval metadata. |
| `harness_id` | No | Optional harness profile override. When omitted, the runtime resolves the default from the authenticated agent profile. |
| `policy_profile_id` | No | Optional policy profile override. When omitted, the runtime resolves the default from the selected harness/profile. |
| `requires_approval` | No | Defaults to `true`. |
| `run_mode` | No | Optional run-mode override. When omitted, the runtime resolves the default from the selected harness/profile. |
| `state` | No | Defaults to `battery_ready`. |

For read-only protocol candidate discovery, callers can use
`tool_id=protocol.discover_candidates` with `plan_mode=single_tool`. The linked
run objective must include `query`; optional objective fields include
`protocol` (`ucp` or `acp`), `brand_id`, `limit`, and `inferred_intent`.
The top-level request `brand_id` is also passed into the seeded discovery action
so brand-scoped and opt-in live retrieval paths do not require duplicate
objective metadata.
For read-only protocol readiness checks, callers can use
`tool_id=protocol.readiness_check` with `plan_mode=single_tool`. The linked run
objective must include `product_id`; optional objective fields include
`protocol` or `protocols`. The top-level request `product_id` is also passed
into the seeded readiness action.

Default harness behavior:

- `run_mode`, `policy_profile_id`, and `harness_id` are now behavior-defining, not future-only metadata.
- For authenticated external agents with an `agent_profile_id`, omitted harness/run-mode/policy values are resolved from that profile and the runtime registry.
- For the built-in `buyer-assistant-v1` profile, the default harness is `safe_autonomy_b2b` and the default run mode is `auto_execute_safe`.
- If the caller provides explicit `harness_id`, `run_mode`, or `policy_profile_id`, the combination must be allowed by the registry profile; incompatible overrides are rejected before a run is created.

Response:

```json
{
  "job": {
    "id": "<job-id>",
    "client_id": "client-a",
    "principal_id": "external-agent-1",
    "agent_profile_id": "buyer-assistant-v1",
    "idempotency_key": "job-123",
    "run_id": "<agent-run-id>",
    "status": "accepted",
    "trace_id": "trace_...",
    "requested_skill_id": "optimize-product-representation",
    "requested_tool_id": "experiment.run_variant",
    "created_at": "...",
    "updated_at": "..."
  },
  "run": {
    "id": "<agent-run-id>",
    "principal_type": "external_agent",
    "principal_id": "external-agent-1",
    "agent_profile_id": "buyer-assistant-v1",
    "harness_id": "safe_autonomy_b2b",
    "policy_profile_id": "safe_auto",
    "run_mode": "auto_execute_safe",
    "status": "planned"
  },
  "idempotent_replay": false
}
```

## Idempotency Semantics

Idempotency scope:

```text
client_id + principal_id + idempotency_key
```

Behavior:

- Same key and same payload returns the existing job/run with `idempotent_replay=true`.
- Exact-payload replays are resolved before current registry/tool/skill validation, so safe retries keep working if runtime metadata or token scopes drift after the first successful create.
- Same key and different payload returns `409 Conflict`.
- Simultaneous same-payload creates can return retryable `409` with `Retry-After`, `X-Agent-Poll-Interval-Seconds`, and a structured `detail.code=idempotency_in_progress`.
- Different principal with the same key creates a different job.

Structured error shape:

```json
{
  "detail": {
    "code": "idempotency_in_progress",
    "message": "idempotent job creation is already in progress; retry with the same idempotency_key",
    "retryable": true,
    "retry_after_seconds": 3
  }
}
```

External-agent endpoints use stable error codes where autonomous callers need branching behavior, including `external_agent_auth_required`, `missing_external_agent_scope`, `missing_tool_scope`, `missing_skill_scope`, `declared_non_executable_tool`, `unsupported_tool`, `unsupported_skill`, `unsupported_capability`, `incompatible_skill_tool`, `invalid_plan_mode`, `invalid_job_plan`, `idempotency_payload_mismatch`, and `idempotency_in_progress`.

`declared_non_executable_tool` means the requested `tool_id` is visible in the registry as a planned or non-executable skill contract, but there is no executable runtime adapter behind it. Current protocol checkout, payment delegation, and browser fallback checkout contracts are intentionally exposed as readiness boundaries so external agents can discover merchant/protocol capability posture for market research without being allowed to trigger checkout, payment, cart, account, or browser transaction side effects. For readiness-boundary tools, the error `context` includes `contract_intent`, `adapter_id`, `blocked_reason`, and the planned `receipt_contract`.

## Get Job Status

Endpoint:

```http
GET /external-agent/jobs/{job_id}
Authorization: Bearer <agent-principal-token>
```

Behavior:

- Only the creating principal can read the job.
- The response includes the linked run.
- Job status is derived from the linked run status.

Status mapping:

| Run status | Job status |
| --- | --- |
| `planned` | `accepted` |
| `running` / `executing` | `running` |
| `completed` | `completed` |
| `failed` | `failed` |
| `paused` | `paused` |
| `canceled` / `cancelled` | `canceled` |

Receipt metadata on the job status payload is only populated when the stored latest receipt matches the current derived job status. Polling endpoints do not mint new receipts implicitly; callers should use `/receipt?refresh=true` when they need a fresh non-terminal attestation.

## Operator Job Supervision

Endpoint:

```http
GET /external-agent/jobs/operator/by-run/{run_id}?client_id=<client>&user_id=<operator>
POST /external-agent/jobs/operator/by-run/{run_id}/receipt/verify?client_id=<client>&user_id=<operator>
```

Behavior:

- These are human-control-plane endpoints, not machine-facing job endpoints.
- They require operator `user_id` context, tenant scoping, and a tenant role of `operator`, `owner`, or `admin`. Platform admins configured through `ADMIN_USER_IDS` are also accepted by the tenant-role helper.
- They let tenant operators inspect the external-agent job linked to a selected `agent_run`, including job id, external principal, idempotency key, requested skill/tool, receipt history, latest receipt, and latest receipt verification.
- Operator job details also include recent normalized `activity_items` for the
  linked run. Protocol discovery and protocol readiness events include the same
  `domain_summary` payloads exposed by the machine activity endpoint.
- They do not mint new receipts. External agents still use `/receipt?refresh=true` when they need to issue a fresh non-terminal attestation.
- They do not relax the principal-scoped machine API. `/external-agent/jobs/{job_id}` and sibling machine endpoints remain readable only by the creating external principal.

## Get Job Receipt

Endpoint:

```http
GET /external-agent/jobs/{job_id}/receipt?refresh=false
Authorization: Bearer <agent-principal-token>
```

Behavior:

- Only the creating principal can read the receipt.
- By default the endpoint returns the stored latest receipt without recomputing evidence or writing a new receipt.
- Use `refresh=true` to mint a fresh non-terminal receipt. Terminal statuses (`completed`, `failed`, `canceled`) may mint a latest-status receipt automatically.
- If no stored receipt exists for a non-terminal job and `refresh=false`, the endpoint returns `404` with guidance to call `refresh=true`.
- The receipt is signed with HMAC-SHA256 and includes a `key_id` for the server-side verifier key family.
- The signed payload covers the job, linked run, principal, status, trace, requested skill/tool, registry pins, and execution evidence digests.
- If the linked run status or signed context changes, a refresh issues and stores a new receipt.
- The latest receipt is also appended to the immutable receipt history.
- Stored receipts returned without refresh can include `stale_context=true` and `refresh_required_for_latest_context=true` when cheap run-level context no longer matches the signed payload.

Example response:

```json
{
  "receipt": {
    "receipt_id": "<receipt-id>",
    "receipt_type": "external_agent_job_accepted",
    "job_id": "<job-id>",
    "run_id": "<agent-run-id>",
    "client_id": "client-a",
    "principal_id": "external-agent-1",
    "status": "accepted",
    "trace_id": "trace_...",
    "requested_skill_id": "optimize-product-representation",
    "requested_tool_id": "experiment.run_variant",
    "registry_version": "agent-runtime-static-v1",
    "registry_fingerprint": "...",
    "key_id": "agent-principal-signing-secret:v1",
    "receipt_context_hash": "<sha256>",
    "evidence": {
      "action_count": 1,
      "event_count": 1,
      "complete": true,
      "actions_complete": true,
      "events_complete": true,
      "action_limit": 500,
      "event_limit": 2000,
      "digest_scope": "complete",
      "latest_event_id": "<event-id>",
      "latest_event_timestamp": "...",
      "action_digest": "<sha256>",
      "event_digest": "<sha256>",
      "terminal_action_statuses": []
    },
    "issued_at": "...",
    "signature": "<payload>.<hmac>",
    "signature_algorithm": "hmac-sha256"
  }
}
```

## Verify Job Receipt

Endpoint:

```http
POST /external-agent/jobs/{job_id}/receipt/verify
Authorization: Bearer <agent-principal-token>
Content-Type: application/json
```

Request:

```json
{
  "receipt": {
    "receipt_id": "<receipt-id>",
    "receipt_type": "external_agent_job_accepted",
    "job_id": "<job-id>",
    "run_id": "<agent-run-id>",
    "client_id": "client-a",
    "principal_id": "external-agent-1",
    "status": "accepted",
    "trace_id": "trace_...",
    "requested_skill_id": "optimize-product-representation",
    "requested_tool_id": "experiment.run_variant",
    "registry_version": "agent-runtime-static-v1",
    "registry_fingerprint": "...",
    "key_id": "agent-principal-signing-secret:v1",
    "receipt_context_hash": "<sha256>",
    "evidence": {
      "action_count": 1,
      "event_count": 1,
      "complete": true,
      "actions_complete": true,
      "events_complete": true,
      "action_limit": 500,
      "event_limit": 2000,
      "digest_scope": "complete",
      "latest_event_id": "<event-id>",
      "latest_event_timestamp": "...",
      "action_digest": "<sha256>",
      "event_digest": "<sha256>",
      "terminal_action_statuses": []
    },
    "issued_at": "...",
    "signature": "<payload>.<hmac>",
    "signature_algorithm": "hmac-sha256"
  }
}
```

Behavior:

- Only the creating principal can verify a receipt against the scoped job.
- Submit the full receipt object returned by `/receipt` or `/receipts`; the signature alone is not enough for `valid_payload=true`.
- The verifier checks the HMAC signature, that the submitted receipt payload matches the signed payload, and that the signed receipt belongs to the scoped job/run/client/principal.
- Response-only metadata fields such as `stale_context` and `refresh_required_for_latest_context` are ignored during payload comparison because they are not part of the signed receipt payload.
- The response includes `valid`, `valid_signature`, `valid_payload`, `valid_scope`, `key_id`, `receipt_payload`, and `blockers`.

## List Job Receipts

Endpoint:

```http
GET /external-agent/jobs/{job_id}/receipts
Authorization: Bearer <agent-principal-token>
```

Behavior:

- Only the creating principal can read the receipt history.
- The response returns signed receipts ordered newest first.
- The endpoint is read-only and does not mint receipts while listing history.
- Each receipt item is the signed payload plus `signature` and `signature_algorithm`.
- Exact same-status/context receipts are deduped by `receipt_context_hash`; same-status state or evidence changes create new history entries only when a caller explicitly refreshes or a terminal status receipt is minted.

Use this endpoint when an external assistant needs to prove the job moved from `accepted` to a later terminal state.

## Get Job Activity

Endpoint:

```http
GET /external-agent/jobs/{job_id}/activity
Authorization: Bearer <agent-principal-token>
```

Behavior:

- Only the creating principal can read the activity projection.
- The response combines job creation, signed receipts, and linked run events into one chronological `items` list.
- The endpoint is polling-safe and read-only; it does not mint receipts.
- Items are normalized as `job`, `receipt`, or `run_event` so external assistants do not have to stitch multiple endpoints together.
- Query params match the run event feed: `event_type`, `status`, `capability_name`, `since`, `until`, `before`, `after`, `event_id`, `around`, and `limit`.
- The response includes `event_page` and `page` with the run-event cursor metadata. `summary.page_scope` is `run_events`.
- Run-event activity items include execution integrity anchors such as `sequence`, `effect_class`, `capability_version`, `is_policy_event`, and event `anchors`. Runtime-created action events populate anchors with `inputs_hash`, `outputs_hash`, registry/tool/skill versions, registry fingerprint, and receipt linkage where available.
- Protocol discovery and protocol readiness run events with receipt evidence
  include `domain_summary` so external assistants can read readiness status,
  readiness score, candidate or protocol counts, source counts where available,
  live/local evidence counts where available, issue counts, and receipt id
  without parsing raw receipt anchors.
  - `protocol_discovery` summaries include `candidate_count`, `source_counts`,
    `live_source_count`, `local_source_count`, `top_blockers`, and
    `top_warnings`.
  - `protocol_readiness` summaries include `protocol_count`, `issue_count`,
    and `top_issues`.

Use this endpoint for machine-friendly progress narration and polling.

Polling responses include `Retry-After`, `X-Agent-Poll-Interval-Seconds`, and `X-Agent-Receipt-Refresh` headers. External agents should treat these as the minimum polling cadence unless a future deployment-specific rate-limit contract is stricter.

## Get Job Events

Endpoint:

```http
GET /external-agent/jobs/{job_id}/events
Authorization: Bearer <agent-principal-token>
```

Behavior:

- Only the creating principal can read the job event feed.
- The endpoint returns the linked run's `agent_events` feed.
- Query params match the run event feed: `event_type`, `status`, `capability_name`, `since`, `until`, `before`, `after`, `event_id`, `around`, and `limit`.

## Current Implementation Boundary

Implemented now:

- `POST /external-agent/jobs`
- `GET /external-agent/credentials/metadata`
- `GET /external-agent/jobs/{job_id}`
- `GET /external-agent/jobs/{job_id}/receipt`
- `GET /external-agent/jobs/{job_id}/receipts`
- `GET /external-agent/jobs/{job_id}/activity`
- `GET /external-agent/jobs/{job_id}/events`
- machine-principal auth requirement
- idempotent create/replay behavior
- idempotency reservation before planning to avoid duplicate planned runs during retry storms
- payload mismatch conflict
- skill/tool scope checks
- linked `agent_run` creation with registry pins, principal, trace id, and initial action plan
- scoped status reads
- signed latest-status receipts
- historical receipt ledger
- job activity projection across job, receipt, and run-event items
- scoped linked-run event reads

Still to build:

- richer domain-specific activity summaries beyond the protocol discovery and
  protocol readiness summaries
- full harness-profile enforcement
- scoped credential management UI/API
- production-grade tool permission registry instead of token-scope strings only
- real ACP/UCP/browser/CLI execution adapters behind the tool contract
