# External Agent Job Contracts

Status: current
Last updated: 2026-05-06

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

Skill/tool scopes:

- Tool request requires `tool:<tool_id>` or `tools:*`.
- Skill request requires `skill:<skill_id>` or `skills:*`.

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
| `cancelled` | `cancelled` |

## Current Implementation Boundary

Implemented now:

- `POST /external-agent/jobs`
- `GET /external-agent/jobs/{job_id}`
- machine-principal auth requirement
- idempotent create/replay behavior
- payload mismatch conflict
- skill/tool scope checks
- linked `agent_run` creation with registry pins, principal, trace id, and initial action plan
- scoped status reads

Still to build:

- signed completion/failure receipts at the job facade level
- richer external-agent job event stream
- full harness-profile enforcement
- scoped credential management UI/API
- production-grade tool permission registry instead of token-scope strings only
- real ACP/UCP/browser/CLI execution adapters behind the tool contract
