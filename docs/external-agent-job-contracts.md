# External Agent Job Contracts

Status: current
Last updated: 2026-05-09

This document defines the machine-facing job contract for external assistants calling the agentic commerce control plane.

The goal is to give external agents a stable, retry-safe API that does not require them to behave like human UI users.

## Contract Principles

- External agents authenticate as `principal_type=external_agent` using signed bearer tokens.
- Every submitted job requires an `idempotency_key`.
- Duplicate submissions with the same principal, tenant, and idempotency key return the same job/run.
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
- optional `agent_profile_id`
- `scopes`

Required scopes:

- `external_agent_jobs:write` or `agent_runs:write` for job creation.
- `external_agent_jobs:read`, `external_agent_jobs:write`, `agent_runs:read`, or `agent_runs:write` for status reads.
- The same read/write scopes allow receipt and event reads.

Skill/tool scopes:

- Tool request requires `tool:<tool_id>` or `tools:*`.
- Skill request requires `skill:<skill_id>` or `skills:*`.
- Registry discovery via `GET /agent-runs/registry` requires a tenant/user context or a bearer token with `external_agent_jobs:read`, `external_agent_jobs:write`, `agent_runs:read`, or `agent_runs:write`.

## Discover Runtime Tools

Endpoint:

```http
GET /agent-runs/registry
Authorization: Bearer <agent-principal-token>
```

Use the registry before creating jobs. Executable tools and capabilities include an `external_agent_contract` block with accepted plan modes, required scope alternatives, candidate/default skills, and a minimal request template. Skill-only declarations that are not accepted by `POST /external-agent/jobs` are marked through `skill_tool_mappings[].executable=false` and listed in `declared_non_executable_skill_tools`.

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
| `harness_id` | No | Stored for future behavior-defining harness profiles. |
| `policy_profile_id` | No | Optional policy profile override. |
| `requires_approval` | No | Defaults to `true`. |
| `run_mode` | No | Defaults to `plan_only`. |
| `state` | No | Defaults to `battery_ready`. |

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
- Different principal with the same key creates a different job.

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

Receipt metadata on the job status payload is only populated when the stored latest receipt matches the current derived job status. If the run status changed after the last receipt was issued, callers should fetch `/receipt` to mint the latest-status receipt.

## Get Job Receipt

Endpoint:

```http
GET /external-agent/jobs/{job_id}/receipt
Authorization: Bearer <agent-principal-token>
```

Behavior:

- Only the creating principal can read the receipt.
- The receipt is signed with HMAC-SHA256.
- The signed payload covers the job, linked run, principal, status, trace, requested skill/tool, and registry pins.
- If the linked run status changes, the endpoint issues and stores a new latest-status receipt.
- The latest receipt is also appended to the immutable receipt history.

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
    "issued_at": "...",
    "signature": "<payload>.<hmac>",
    "signature_algorithm": "hmac-sha256"
  }
}
```

## List Job Receipts

Endpoint:

```http
GET /external-agent/jobs/{job_id}/receipts
Authorization: Bearer <agent-principal-token>
```

Behavior:

- Only the creating principal can read the receipt history.
- The response returns signed receipts ordered newest first.
- The endpoint ensures a latest-status receipt exists before listing history.
- Each receipt item is the signed payload plus `signature` and `signature_algorithm`.

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
- Items are normalized as `job`, `receipt`, or `run_event` so external assistants do not have to stitch multiple endpoints together.
- Query params match the run event feed: `event_type`, `status`, `capability_name`, `since`, `until`, `before`, `after`, `event_id`, `around`, and `limit`.
- The response includes `event_page` and `page` with the run-event cursor metadata. `summary.page_scope` is `run_events`.

Use this endpoint for machine-friendly progress narration and polling.

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
- `GET /external-agent/jobs/{job_id}`
- `GET /external-agent/jobs/{job_id}/receipt`
- `GET /external-agent/jobs/{job_id}/receipts`
- `GET /external-agent/jobs/{job_id}/activity`
- `GET /external-agent/jobs/{job_id}/events`
- machine-principal auth requirement
- idempotent create/replay behavior
- payload mismatch conflict
- skill/tool scope checks
- linked `agent_run` creation with registry pins, principal, trace id, and initial action plan
- scoped status reads
- signed latest-status receipts
- historical receipt ledger
- job activity projection across job, receipt, and run-event items
- scoped linked-run event reads

Still to build:

- richer domain-specific activity summaries beyond normalized event projection
- full harness-profile enforcement
- scoped credential management UI/API
- production-grade tool permission registry instead of token-scope strings only
- real ACP/UCP/browser/CLI execution adapters behind the tool contract
