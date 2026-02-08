# Validation MCP Tooling (Draft)

This app exposes validation endpoints that can be wrapped as MCP tools. The MCP
server itself is not bundled in this repo yet; use these schemas when wiring a
server (Claude Code / OpenAI Apps SDK / Gemini function-calling adapter).

Provider keys can be checked via `GET /health/llm`.

## Tools

```json
[
  {
    "name": "validation.create_job",
    "description": "Create a validation job for an experiment run, simulation run, or battery.",
    "input_schema": {
      "type": "object",
      "properties": {
        "entity_type": { "enum": ["experiment_run", "simulation_run", "battery"] },
        "entity_id": { "type": "string" },
        "client_id": { "type": "string" },
        "brand_id": { "type": "string" },
        "product_id": { "type": "string" },
        "provider": { "enum": ["openai", "gemini", "claude"] },
        "mode": { "enum": ["in_app", "external"] },
        "model": { "type": "string" },
        "prompt_version": { "type": "string" },
        "input_payload": { "type": "object" },
        "requested_by": { "type": "string" }
      },
      "required": ["entity_type", "entity_id", "client_id", "provider", "mode", "input_payload"]
    }
  },
  {
    "name": "validation.run_job",
    "description": "Execute in-app validation (BYOK) and persist results.",
    "input_schema": {
      "type": "object",
      "properties": { "job_id": { "type": "string" } },
      "required": ["job_id"]
    }
  },
  {
    "name": "validation.submit_external_result",
    "description": "Submit structured JSON from an external provider.",
    "input_schema": {
      "type": "object",
      "properties": {
        "job_id": { "type": "string" },
        "provider": { "enum": ["openai", "gemini", "claude"] },
        "model": { "type": "string" },
        "structured_result": { "type": "object" },
        "raw_response": { "type": "string" }
      },
      "required": ["job_id", "structured_result"]
    }
  },
  {
    "name": "validation.get_job",
    "description": "Fetch a job and its latest result.",
    "input_schema": {
      "type": "object",
      "properties": { "job_id": { "type": "string" } },
      "required": ["job_id"]
    }
  },
  {
    "name": "validation.list_jobs",
    "description": "List validation jobs by client or entity.",
    "input_schema": {
      "type": "object",
      "properties": {
        "client_id": { "type": "string" },
        "entity_type": { "enum": ["experiment_run", "simulation_run", "battery"] },
        "entity_id": { "type": "string" },
        "limit": { "type": "integer", "default": 50 }
      },
      "required": ["client_id"]
    }
  }
]
```

## Endpoint Mapping

- `validation.create_job` → `POST /validation/jobs`
- `validation.run_job` → `POST /validation/jobs/{id}/run`
- `validation.submit_external_result` → `POST /validation/jobs/{id}/external`
- `validation.get_job` → `GET /validation/jobs/{id}`
- `validation.list_jobs` → `GET /validation/jobs`

## External Result Schema

```json
{
  "winner_id": "variant_a",
  "score": 0.72,
  "confidence": 0.81,
  "evidence_strength": "moderate",
  "rationale_bullets": ["..."],
  "flags": ["over_specificity"]
}
```
