# Adapter Setup

## Shopify
1. Create a private app with read-only product access.
2. Set `CATALOG_SOURCE=shopify` in `.env`.
3. Provide `SHOPIFY_DOMAIN` and `SHOPIFY_TOKEN` via `.env` or environment vars.
4. Run the FastAPI surface (`uvicorn api.main:app --reload`) or the orchestration runtime to pull live merchant catalogs.

## Google Shopping (Mock)
- Set `CATALOG_SOURCE=google_shopping` to use the deterministic mock data.

## Google Merchant Center
1. Export your Merchant Center feed as JSON and save the path.
2. Set `CATALOG_SOURCE=google_merchant` and `GOOGLE_MERCHANT_FEED_PATH=/path/to/feed.json`.
3. The adapter validates required fields and assigns confidence scores that
   reflect this third-party discovery surface.
