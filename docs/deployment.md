# Deployment & Runtime Guide

## 1. Local Environment

1. Copy `.env.example` to `.env` and set `CATALOG_SOURCE` along with any
   adapter-specific variables (e.g., `SHOPIFY_DOMAIN`, `GOOGLE_MERCHANT_FEED_PATH`).
2. Create a virtual environment (uv recommended):
   ```bash
   uv venv venv
   source venv/bin/activate
   uv pip install -r requirements.txt
   ```
3. Run the Gradio demo locally:
   ```bash
   python -m demos.gradio.app
   ```
4. Switch data sources by updating `CATALOG_SOURCE` and restarting the demo.

## 2. FastAPI Runtime

Expose the search/feed APIs via FastAPI:
```bash
export CATALOG_SOURCE=google_merchant  # or shopify/mock
uvicorn api.main:app --reload --port 8000
```
The API now serves `/products/search` using whichever adapter you enabled.

## 3. Hugging Face Spaces

1. Copy the repository (or subset) into a new Space.
2. Ensure `requirements.txt` is present (Spaces installs dependencies from this file).
3. Set the Space entry point to `hf_space/app.py`. This module imports the shared
   Gradio Blocks from `demos.gradio.app` so the same UI runs both locally and in
   the cloud.
4. Configure Space secrets for `CATALOG_SOURCE`, `SHOPIFY_DOMAIN`, etc., via the
   Hugging Face Secrets UI.

## 4. Attribution Exports

When running the Gradio demo locally, attribution events are buffered in-memory
via `attribution.events`. Export them for GA4 verification:
```bash
python -m attribution.ga4_export --path ga4_events.json
```
This creates a JSON payload you can inspect or feed into downstream systems.
