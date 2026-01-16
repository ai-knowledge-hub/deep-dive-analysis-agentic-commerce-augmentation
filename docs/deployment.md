# Deployment & Runtime Guide

## 1. Environment Profiles

| Environment | Catalog | LLM Provider | DB Path | Notes |
|-------------|---------|--------------|---------|-------|
| **Local** | `mock` | `openrouter` | `./tmp/local.db` | Requires `OPENROUTER_API_KEY`. Avoids Gemini quota. |
| **Dev / Preview** | `google_merchant` | `gemini` | `./db/empowerment.dev.db` | Limited `GOOGLE_API_KEY`, telemetry optional. |
| **Production** | `google_merchant` | `gemini` | `/var/lib/app/prod.db` | Real feeds, full telemetry, rate-limit logging. |

Copy the relevant section from `.env.example` into `.env.local` (local) or configure as platform secrets (dev/prod).

---

## 2. Local Development

### Backend (FastAPI)

```bash
# 1. Configure environment
cp .env.example .env.local
# Edit .env.local: set OPENROUTER_API_KEY, OPENROUTER_MODEL

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Start server
uvicorn api.main:app --reload --port 8000
```

### Frontend (Next.js)

```bash
cd web
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL if API is remote
pnpm install
pnpm dev
```

Visit `http://localhost:3000` to interact with the assistant.

---

## 3. Production Deployment

### Railway (Backend)

1. Connect your GitHub repository
2. Set environment variables:
   - `CATALOG_SOURCE=google_merchant`
   - `GOOGLE_MERCHANT_FEED_PATH=/path/to/feed.json`
   - `LLM_PROVIDER=gemini`
   - `GOOGLE_API_KEY=your-key`
   - `GEMINI_MODEL=gemini-2.0-flash`
3. Deploy with: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

### Vercel (Frontend)

1. Connect `web/` directory
2. Set `NEXT_PUBLIC_API_URL` to your Railway backend URL
3. Deploy automatically on push

---

## 4. Catalog Sources

Set `CATALOG_SOURCE` to choose the product adapter:

| Source | Environment Variables | Use Case |
|--------|----------------------|----------|
| `mock` | None | Local development, testing |
| `shopify` | `SHOPIFY_DOMAIN`, `SHOPIFY_TOKEN` | Live Shopify store |
| `google_shopping` | None | Deterministic mock data |
| `google_merchant` | `GOOGLE_MERCHANT_FEED_PATH` | Google Merchant Center feed |

---

## 5. LLM Providers

Set `LLM_PROVIDER` to choose the language model:

| Provider | Environment Variables | Best For |
|----------|----------------------|----------|
| `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Local dev (cost-effective) |
| `gemini` | `GOOGLE_API_KEY`, `GEMINI_MODEL` | Production (Gemini 2.0/3.0) |

---

## 6. Attribution Exports

Export attribution events for analytics verification:

```bash
python -m modules.attribution.ga4_export --path ga4_events.json
```

This creates a JSON payload compatible with GA4 or custom dashboards.

---

## 7. Health Checks

```bash
# Verify product search
curl "http://localhost:8000/products/search?query=workspace"

# Verify conversation API
curl -X POST "http://localhost:8000/conversation/start" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}'

# Run test suite
make test
```

---

See [docs/adapters.md](./adapters.md) for detailed adapter configuration.
