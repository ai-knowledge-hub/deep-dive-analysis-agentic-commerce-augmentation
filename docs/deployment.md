# Deployment & Runtime Guide

Status: current
Last verified: 2026-09-05
Baseline: `origin/main@96a1c23` (includes PR #120)

## 1. Environment Profiles

| Environment | LLM Provider | DB Path | Notes |
|-------------|--------------|---------|-------|
| **Local** | `openrouter` | `runtime-path:./tmp/local.db` | Requires `OPENROUTER_API_KEY`. Avoids Gemini quota. |
| **Dev / Preview** | `gemini` | `runtime-path:./tmp/empowerment.dev.db` | Limited `GOOGLE_API_KEY`, telemetry optional. |
| **Production** | `gemini` | `runtime-path:/var/lib/app/prod.db` | Full telemetry, rate-limit logging. |

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

### Approval and governed-effect migrations

Migrations 044-049 are one ordered compatibility sequence:

- 044 creates durable approval effect execution;
- 045 adds immutable start/provenance snapshots and quarantines legacy starts;
- 046 binds validation jobs to the frozen requested model;
- 047 creates governed effect receipts;
- 048 expands receipt scope and relationship validation; and
- 049 preserves a relationship-validating compatibility path for the previous
  application writer before strict scope enforcement.

Apply migrations before deploying the current writer. Do not skip directly to
strict receipt enforcement, edit an already-applied migration, or roll the app
back to a writer older than the 049 compatibility contract without quiescing
governed effects. After rollout, inspect uncertain effects and use the
tenant-authorized `reconcile_effect` command; do not repair approval/effect
rows directly.

#### Post-migration inspection

Run these read-only checks against the deployed database immediately after
migration, after application rollout, and before rollback:

```bash
sqlite3 "$(make -s db-path)" <<'SQL'
SELECT status, COUNT(*) AS total
FROM approval_effect_executions
GROUP BY status;

SELECT execution_id, tenant_id, workflow_id, action_id, status, started_at,
       error_code
FROM approval_effect_executions
WHERE status = 'uncertain'
   OR (status = 'started'
       AND julianday(started_at) <= julianday('now', '-15 minutes'))
ORDER BY started_at;

SELECT scope_status, COUNT(*) AS total
FROM governed_effect_receipts
GROUP BY scope_status;

SELECT receipt_id, tenant_id, workflow_id, action_id, source_metric_id,
       scope_status, created_at
FROM governed_effect_receipts
WHERE scope_status IN ('invalid_legacy', 'unverified_legacy')
ORDER BY created_at;

SELECT execution_id, tenant_id, workflow_id, action_id, started_at
FROM approval_effect_executions
WHERE authorization_snapshot_json IS NULL
   OR authorization_snapshot_digest IS NULL
ORDER BY started_at;

SELECT effect.execution_id, effect.tenant_id, effect.workflow_id,
       effect.action_id, effect.started_at,
       MAX(command.created_at) AS last_reconcile_requested_at
FROM approval_effect_executions AS effect
LEFT JOIN agent_events AS command
  ON command.agent_run_id = effect.workflow_id
 AND command.action_id = effect.action_id
 AND command.event_type = 'operator_command_reconcile_effect'
WHERE effect.status = 'uncertain'
GROUP BY effect.execution_id, effect.tenant_id, effect.workflow_id,
         effect.action_id, effect.started_at
ORDER BY effect.started_at;
SQL
```

Alert on any `invalid_legacy` or `unverified_legacy` receipt, any effect
remaining `started` for more than 15 minutes, or any `uncertain` effect
older than 15 minutes. The threshold is an initial operational default, not
proof that an external effect failed. The final query shows whether a
`reconcile_effect` command was received for the same workflow and action; it
is a request signal, not acknowledgement or proof of recovery. The durable
`approval_effect_executions` row remains the outcome authority.

There is no persisted operator-acknowledgement contract yet. Command events do
not carry approval or effect-execution identity, and effect events do not carry
the execution ID needed for a complete event-only join. Durable acknowledgement
is planned under SEC-17. Until that control is implemented, alert resolution
must be recorded in the external incident/on-call system and closed only after
the durable effect row becomes `succeeded` or an explicit operator disposition
is recorded outside this application.

#### Recovery and disposition

1. For an `uncertain` effect, inspect the exact effect-start record and bound
   provider or governed-effect evidence. Preflight recovery through:

   ```bash
   curl -X POST "$BACKEND_URL/agent-runs/$RUN_ID/commands/preflight" \
     -H "Authorization: Bearer $AGENT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"client_id":"'"$CLIENT_ID"'","command_type":"reconcile_effect","action_id":"'"$ACTION_ID"'"}'
   ```

2. If preflight is allowed and the evidence identifiers match, submit the same
   payload to `POST /agent-runs/{run_id}/commands` with a unique
   `idempotency_key`. Reconciliation records an existing outcome; it does not
   execute the effect again.
3. Treat `invalid_legacy` as quarantined evidence. Do not promote it to
   `validated`, use it to fulfill approval, or delete it. Investigate the
   tenant/experiment/variant/source-metric relationship and retain the record
   for audit or incident response.
4. `unverified_legacy` is only a migration/previous-writer input state. The
   compatibility trigger promotes it to `validated` only when the complete
   relationship is authoritative. A row that remains unverified blocks rollout
   completion and requires investigation; do not update it manually.
5. An effect start without an authorization snapshot is legacy quarantined
   state and cannot be automatically reconciled. Confirm the provider outcome,
   prevent re-execution, and escalate for an explicit operator disposition.

#### Rollout and rollback decision

- Before rollout, record the query result sets above and quiesce governed
  workers if any migration is pending.
- Deploy migrations 044-049 in filename order, run the inspection, then deploy
  the current writer and inspect again.
- Migration 049 supports the immediately previous receipt writer only when its
  output contains a valid source metric and the full relationship resolves.
- Keep schema migrations in place during application rollback. If the rollback
  target predates that compatibility contract, quiesce governed effects first;
  otherwise it may create uncertain work or fail every promotion.
- Do not complete rollout or rollback while there are unexplained invalid,
  unverified, stale-started, or uncertain records. Preserve their rows and
  correlated events as the recovery audit trail.

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
