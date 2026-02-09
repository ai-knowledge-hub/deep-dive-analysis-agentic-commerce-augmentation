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

## 6) External Analytics Validation Ingestion

Purpose:
- Ingest externally collected validation/analytics events into the app's validation system.

Current status:
- Generic ingestion exists.
- Native GA4 connector is planned, not built.

---

## 7) Integration Selection Guidance

Use this rule of thumb:
- Need fastest local loop: `in_app_byok` synthetic validation.
- Need provider-native execution with callback: `provider_openai_mcp`.
- Need fallback when provider callback cannot be used: `manual_fallback`.
- Need production confidence decisions: prioritize observed reality validation over synthetic signal.
