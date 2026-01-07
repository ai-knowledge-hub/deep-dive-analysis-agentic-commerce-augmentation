# Deployment & Runtime Guide

## 1. Environment Profiles

| Environment | Catalog | LLM Provider | DB Path | Notes |
|-------------|--------|--------------|---------|-------|
| **Local** (`.env.local`) | `mock` | `openrouter` | `./tmp/local.db` | Requires `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. Avoids spending Gemini quota. |
| **Dev / Preview** (`.env.dev` or secrets) | `google_merchant` (or Shopify) | `gemini` | `./db/empowerment.dev.db` | Limited `GOOGLE_API_KEY`, telemetry optional. |
| **Prod** (platform secrets) | `google_merchant` | `gemini` | `/var/lib/app/prod.db` | Real feeds/telemetry, rate-limit logging on. |

When developing locally, export:
```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
export CATALOG_SOURCE=mock
export DATABASE_PATH=./tmp/local.db
```

> Tip: Set `OPENROUTER_SITE_URL` and `OPENROUTER_APP_NAME` so OpenRouter can associate usage with your dev environment.

For dev/prod deployments, keep `LLM_PROVIDER=gemini` and set `GOOGLE_API_KEY`/`GEMINI_MODEL` as needed.

## 2. Local Backend

1. Copy `.env.example` → `.env.local` and adjust the *Local* section (catalog, OpenRouter, DB path).
2. Create a virtual environment (uv recommended):
   ```bash
   uv venv venv
   source venv/bin/activate
   uv pip install -r requirements.txt
   ```
3. Start FastAPI:
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

## 3. Next.js Frontend

```bash
cd web
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL if the API is remote
pnpm install
pnpm dev
```

Visit `http://localhost:3000` to interact with the assistant.

## 4. Attribution Exports

Attribution events are buffered in-memory via `attribution.events`. Export them for GA4 verification:
```bash
python -m attribution.ga4_export --path ga4_events.json
```
This creates a JSON payload you can inspect or feed into downstream systems.
