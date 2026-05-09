# Deployment & Runtime Guide

## 1. Environment Profiles

| Environment | LLM Provider | DB Path | Notes |
|-------------|--------------|---------|-------|
| **Local** | `openrouter` | `./tmp/local.db` | Requires `OPENROUTER_API_KEY`. Avoids Gemini quota. |
| **Dev / Preview** | `gemini` | `./tmp/empowerment.dev.db` | Limited `GOOGLE_API_KEY`, telemetry optional. |
| **Production** | `gemini` | `/var/lib/app/prod.db` | Full telemetry, rate-limit logging. |

Copy the relevant section from `.env.example` into `.env.local` (local) or configure as platform secrets (dev/prod).

---

## 2. Local Development

### Backend (FastAPI)

```bash
# 1. Configure environment
cp .env.example .env.local
# Edit .env.local: set OPENROUTER_API_KEY, OPENROUTER_MODEL
# Optional: ADMIN_USER_IDS=user_123,user_456 (bypass client_id requirement)
# Optional: CLERK_WEBHOOK_SECRET=whsec_... (for Clerk user sync)
# Optional: ENABLE_PROVIDER_VALIDATION_INTEGRATIONS=true
# Optional: BACKEND_PUBLIC_URL=http://localhost:8000
# Optional: VALIDATION_CALLBACK_SIGNING_SECRET=change-me

# 2. Install dependencies
uv sync --extra dev

# 3. Start server (use uv to ensure the venv is active)
uv run uvicorn api.main:app --reload --port 8000
```

### Frontend (Next.js)

```bash
cd web
cp ../.env.example .env.local
# Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY + CLERK_SECRET_KEY
# Optional: set NEXT_PUBLIC_API_URL if API is remote
# Required: NEXT_PUBLIC_CLIENT_ID=default (or your tenant id)
pnpm install
pnpm dev
```

Visit `http://localhost:3000` to interact with the assistant.

### Database helpers (local)

```bash
make db-init
make db-migrate
make db-path
make seed-demo
```

Notes:
- `db-migrate` currently re-applies schema bootstrap (SQLite helper), not Alembic-style versioned migrations.
- Use the same `DATABASE_PATH` for init/seed/run to keep tenant data consistent.
- Canonical schema and migrations are under `shared/db/schema.sql` and `shared/db/migrations/*.sql`.
- Runtime DB adapters are grouped under `infrastructure/db/{core,agent,experiment,validation,loop,catalog,session,search}`.

---

## 3. Production Deployment

### Backend (Python Runtime)

1. Connect your GitHub repository
2. Set environment variables:
   - `LLM_PROVIDER=gemini`
   - `GOOGLE_API_KEY=your-key`
   - `GEMINI_MODEL=gemini-2.0-flash`
3. Deploy with: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

### Frontend (Vercel)

1. Connect `web/` directory
2. Set `NEXT_PUBLIC_API_URL` to your Railway backend URL
3. Set Clerk env vars (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`,
   `NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL`,
   `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL`)
4. Deploy automatically on push

### Vercel (Full‑stack) — Planned, Not Built

It is **not** currently configured to deploy the FastAPI backend on Vercel’s Python
runtime. This would require:
- Serverless adaptation of FastAPI routes.
- Replacing local SQLite with an external DB.
- Explicit Vercel config for functions.
- Runtime constraints testing for long experiment/simulation requests.

Consider this **planned** work rather than a supported deployment path today.

---

## 4. LLM Providers

Set `LLM_PROVIDER` to choose the language model:

| Provider | Environment Variables | Best For |
|----------|----------------------|----------|
| `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Local dev (cost-effective) |
| `gemini` | `GOOGLE_API_KEY`, `GEMINI_MODEL` | Production (Gemini 2.0/3.0) |

---

## 5. Validation Runtime Terminology

The app uses two distinct validation signals in production:

1. **Synthetic validation signal**
- Provider/model-run validation jobs (BYOK).
- Modes:
  - `in_app_byok` (immediate)
  - `provider_openai_mcp` (provider-run via ChatGPT + callback)
  - `manual_fallback` (structured paste-back)
  - `provider_gemini_function` (contracted, currently not implemented at runtime)
- Purpose: fast screening and consistency checks.

2. **Observed reality signal**
- Manual/external logs of what actually surfaced on real platforms.
- Purpose: grounding and calibration of the loop.

Use observed reality signal as higher-trust evidence for rollout decisions.

### Provider-run synthetic validation env vars

Required to enable provider-run flow:
- `ENABLE_PROVIDER_VALIDATION_INTEGRATIONS=true`
- `BACKEND_PUBLIC_URL` (public backend URL used to build callback endpoint)
- `VALIDATION_CALLBACK_SIGNING_SECRET` (HMAC secret for callback signing/verification)
- `REGISTRY_APPROVAL_SIGNING_SECRET` (HMAC secret for registry ownership approval receipts; falls back to `AGENT_PRINCIPAL_SIGNING_SECRET` outside production)
- `AGENT_PRINCIPAL_SIGNING_SECRET` (HMAC secret for external/internal agent bearer tokens)

Optional:
- `VALIDATION_CALLBACK_TTL_SECONDS` (default: `900`)
- `AGENT_PRINCIPAL_TOKEN_TTL_SECONDS` (default: `3600`)
- `AGENT_PRINCIPAL_TOKEN_MAX_TTL_SECONDS` (default: `3600`)
- `AGENT_PRINCIPAL_TOKEN_AUDIENCE` (default: `agent-runtime`)
- `AGENT_PRINCIPAL_TOKEN_ISSUER` (default: `deep-dive-analysis-agentic-commerce-augmentation`)
- `OPENAI_MCP_LAUNCH_URL` (default: `https://chatgpt.com/`)
- `GEMINI_FUNCTION_LAUNCH_URL` (default: `https://gemini.google.com/`)

---

## 6. Attribution Exports

**Planned (not built):** attribution export utilities.

---

## 7. Health Checks

```bash
# Verify product search (requires client_id)
curl "http://localhost:8000/products/search?query=workspace&client_id=default"

# Verify conversation API
curl -X POST "http://localhost:8000/conversation/start" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}'

# Run test suite
make test
```

---
