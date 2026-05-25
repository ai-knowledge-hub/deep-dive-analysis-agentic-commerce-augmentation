# External Integrations Guide

This document lists the app's external integrations, what each one is for, and how each works in the current implementation.

---

## 1) LLM Providers (BYOK)

Purpose:
- Power chat/generation, simulation/experiments, and synthetic validation.

Supported providers:
- OpenRouter
- OpenAI
- Anthropic
- Gemini

How it works:
1. Configure provider API key + model in Admin -> Model Gateway.
2. Set active provider/model for chat/generation and validation (can differ).
3. Backend routes provider calls through configured adapters.

Key env vars:
- `LLM_PROVIDER`
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_VALIDATION_MODEL`
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_VALIDATION_MODEL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_VALIDATION_MODEL`
- `GOOGLE_API_KEY`, `GEMINI_MODEL`, `GEMINI_VALIDATION_MODEL`

---

## 2) Validation Provider Run: ChatGPT MCP (OpenAI)

Purpose:
- Run synthetic validation in provider UX while preserving structured callback into this app.

Current status:
- Implemented end-to-end.

How it works:
1. Create validation job with mode `provider_openai_mcp`.
2. Start provider run: `POST /validation/jobs/{job_id}/start-provider-run`.
3. Backend returns launch contract (`launch_url`, setup instructions, `provider_run_id`, callback metadata).
4. User completes run in ChatGPT.
5. Provider callback returns to `POST /validation/jobs/{job_id}/provider-callback`.
6. Backend verifies callback token/signature and persists normalized result + scores.

Security controls:
- Signed callback token (`VALIDATION_CALLBACK_SIGNING_SECRET`).
- Token TTL (`VALIDATION_CALLBACK_TTL_SECONDS`).
- Replay prevention via consumed callback token store.
- Mode/provider/job/provider-run matching checks before persist.

Key env vars:
- `ENABLE_PROVIDER_VALIDATION_INTEGRATIONS=true`
- `BACKEND_PUBLIC_URL`
- `VALIDATION_CALLBACK_SIGNING_SECRET`
- Optional: `OPENAI_MCP_LAUNCH_URL`

---

## 3) Validation Provider Run: Gemini Function Call

Purpose:
- Same provider-run validation concept for Gemini.

Current status:
- UI/API contract is present (`provider_gemini_function`), runtime execution is not implemented yet (`501`).

How it is expected to work when enabled:
1. Create job in `provider_gemini_function` mode.
2. Start provider run and open Gemini launch URL.
3. Complete provider task and submit verified callback.
4. Persist normalized result and scoring.

Key env vars:
- `GEMINI_FUNCTION_LAUNCH_URL` (launch target)

---

## 4) Clerk Authentication

Purpose:
- User authentication/session handling for the web app.

How it works:
1. Frontend uses Clerk publishable key and routes.
2. Backend can process Clerk webhooks for user sync/events.

Key env vars:
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CLERK_WEBHOOK_SECRET`
- Clerk route vars (`NEXT_PUBLIC_CLERK_SIGN_IN_URL`, etc.)

---

## 5) Search/Research Integrations

### SerpAPI (optional)
Purpose:
- Enable Google-like search results in research paths.

Key env var:
- `SERPAPI_API_KEY`

### MCP `web_fetch` allowlist
Purpose:
- Control which hosts can be fetched during web-enabled research.

Key env vars:
- `WEB_FETCH_ALLOWLIST`
- `WEB_FETCH_ALLOW_ALL` (dev-only override)

---

## 6) Protocol Discovery And Readiness

Purpose:
- Let agent runs inspect ACP/UCP readiness through read-only adapter receipts
  before any external side-effecting execution is introduced.

Current status:
- `protocol.readiness.v1` and `protocol.discovery.v1` are implemented as
  read-only execution adapters.
- UCP readiness supports the older bundled `2026-01-11` schema fixture and the
  current public `2026-04-08` profile shape using structural validation for
  services, capabilities, payment handlers, signing keys, HTTPS endpoints, and
  supported-version metadata.
- ACP readiness tracks the current `2026-04-17` beta posture for checkout
  capability negotiation and delegate-payment readiness.
- Candidate discovery falls back to DB/metadata-backed records when live
  protocol surfaces are not configured or fail validation.
- UCP live catalog discovery is available for read-only `/catalog/search` when
  a brand explicitly opts in through metadata and the merchant host is
  allowlisted.
- ACP live feed discovery is available for read-only product feed URLs when a
  brand explicitly opts in through metadata and the merchant host is allowlisted.
- Checkout, delegated-payment, and browser checkout fallback readiness
  boundaries are visible in the runtime registry as `status=planned`,
  `contract_intent=readiness_boundary` external-side-effect contracts, but they
  have no allowed executable capabilities.
- These readiness boundaries support merchant/protocol intelligence, not real
  transactions. They expose an `external_write_execution` receipt contract only
  as a guardrail for future implementation review. The contract requires
  approval linkage, idempotency, external operation identifiers,
  request/response fingerprints, verification status, adapter-specific evidence
  fields, and a linked run event.

Current external reference points:
- UCP business profiles are discovered at `/.well-known/ucp`.
- ACP is treated as a beta checkout/delegate-payment surface with
  date-versioned snapshots.
- Product discovery for ACP/OpenAI commerce flows uses a structured product
  feed with eligibility flags such as `is_eligible_search` and
  `is_eligible_checkout`.

Still planned:
- Broader ACP/UCP retrieval adapters for additional live merchant surfaces.
- Strict local UCP `2026-04-08` schema bundle if offline schema validation is
  required.
- Broader checkout/payment/browser/CLI readiness probes only where they remain
  non-transactional and evidence-only.

UCP live discovery config:

```json
{
  "ucp": {
    "live_discovery": {
      "enabled": true,
      "profile_url": "https://merchant.example/.well-known/ucp",
      "agent_profile_url": "https://platform.example/ucp/profile"
    }
  }
}
```

Equivalent inline profile support:

```json
{
  "ucp": {
    "live_discovery": { "enabled": true }
  },
  "ucp_profile": {
    "ucp": {
      "version": "2026-04-08",
      "services": {
        "dev.ucp.shopping": [
          {
            "version": "2026-04-08",
            "transport": "rest",
            "endpoint": "https://merchant.example/ucp",
            "schema": "https://ucp.dev/2026-04-08/services/shopping/rest.openapi.json"
          }
        ]
      },
      "capabilities": {
        "dev.ucp.shopping.checkout": [{ "version": "2026-04-08" }],
        "dev.ucp.shopping.catalog.search": [{ "version": "2026-04-08" }]
      },
      "payment_handlers": {}
    },
    "signing_keys": []
  }
}
```

Required env:
- `PROTOCOL_FETCH_ALLOWLIST=merchant.example`

Optional env:
- `PROTOCOL_ALLOW_ALL_HOSTS=true` is development-only and should not be used for
  production.

Live UCP discovery always requires explicit brand-level opt-in through
`ucp.live_discovery.enabled`, `ucp.live_discovery_enabled`, or
`ucp_live_discovery_enabled`. Redirects are rejected if the final response URL
crosses to a different host than the originally allowlisted merchant host.

ACP live discovery config:

```json
{
  "acp": {
    "live_discovery": {
      "enabled": true,
      "feed_url": "https://merchant.example/acp/products.json"
    }
  }
}
```

Supported feed response shapes:
- JSON object with `products`, `items`, or `data` array.
- JSON array of product objects.
- JSONL, one product object per line.
- CSV with product fields as headers.

Feed records are treated as read-only evidence. The adapter only returns records
with `is_eligible_search=true` or `enable_search=true`.

Discovery provenance:
- Each returned candidate includes `discovery_source`, currently one of:
  - `ucp_catalog_search`
  - `acp_product_feed`
  - `ucp_local_metadata`
  - `acp_local_metadata`
- The adapter receipt evidence includes `source_counts` so operators and
  external callers can audit whether a result set came from live protocol
  retrieval or local fallback metadata.
- Discovery summaries and adapter receipts also include `readiness_summary`,
  a compact market-research signal with ready, warning, and blocked candidate
  counts, protocol/source counts, live versus local evidence counts, and a
  0-100 score. This summarizes merchant protocol readiness only; it does not
  authorize checkout, delegated payment, or browser fallback execution.

Required env:
- `PROTOCOL_FETCH_ALLOWLIST=merchant.example`

Live ACP discovery always requires explicit brand-level opt-in through
`acp.live_discovery.enabled`, `acp.live_discovery_enabled`, or
`acp_live_discovery_enabled`. Redirects are rejected if the final response URL
crosses to a different host than the originally allowlisted merchant host.

---

## 7) External Analytics Validation Ingestion

Purpose:
- Ingest externally collected validation/analytics events into the app's validation system.

Current status:
- Generic ingestion exists.
- Native GA4 connector is planned, not built.

---

## 8) Integration Selection Guidance

Use this rule of thumb:
- Need fastest local loop: `in_app_byok` synthetic validation.
- Need provider-native execution with callback: `provider_openai_mcp`.
- Need fallback when provider callback cannot be used: `manual_fallback`.
- Need production confidence decisions: prioritize observed reality validation over synthetic signal.

---

## 9) Agent Operator Mode (Planned)

Planned: agents can request validations and use the same provider integrations, but they will do so through a capability registry and policy enforcer (not raw route calls).

Reference: `docs/agentic-layer.md`.
