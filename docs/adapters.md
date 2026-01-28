# Commerce Adapters

The platform loads products via adapters that transform external catalog formats into our intent-legible product model. Each adapter emits `RawOffer` objects that flow through the `RawOffer → RawProduct → Product` pipeline, with optional intentionality enrichment.

## Available Adapters

| Adapter | Source | Confidence | Use Case |
|---------|--------|------------|----------|
| `mock` | Built-in test data | High | Development, testing |
| `shopify` | Shopify Storefront API | High | First-party merchant data |
| `google_shopping` | Mock Google Shopping | Medium | Testing aggregated flows |
| `google_merchant` | Merchant Center JSON feed | Medium | Production aggregated data |
| `ucp` | Universal Commerce Protocol | Low | Adapter stub (discovery) |

---

## Mock Adapter

For local development and testing.

```bash
# .env.local
CATALOG_SOURCE=mock
```

No additional configuration required. When `CATALOG_SOURCE=mock`, the catalog stream is disabled and the UI shows research insights only to avoid misleading recommendations.

---

## Shopify Adapter

Connects to a live Shopify store via the Storefront API.

### Setup

1. Create a private app in Shopify Admin with **read-only product access**
2. Note your store domain and access token

### Configuration

```bash
# .env.local or .env
CATALOG_SOURCE=shopify
SHOPIFY_DOMAIN=your-store.myshopify.com
SHOPIFY_TOKEN=your-storefront-access-token
```

### Notes

- Returns high-confidence data (first-party source)
- Supports variant-level product information
- Respects Shopify API rate limits

---

## Google Merchant Center Adapter

Loads products from an exported Merchant Center feed.

### Setup

1. Export your Merchant Center feed as JSON
2. Save to a local path or cloud storage

### Configuration

```bash
# .env.local or .env
CATALOG_SOURCE=google_merchant
GOOGLE_MERCHANT_FEED_PATH=/absolute/path/to/google_merchant_feed.json
```

### Feed Format

Each entry must include standard Merchant Center fields:

```json
{
  "id": "product-123",
  "title": "Product Name",
  "description": "Product description",
  "price": { "value": "29.99", "currency": "USD" },
  "availability": "in_stock",
  "link": "https://merchant.com/product-123",
  "image_link": "https://merchant.com/images/product-123.jpg"
}
```

### Notes

- Assigned **medium confidence** (aggregated discovery surface)
- Alignment scoring considers data quality for inference
- See `data/google_merchant_feed.json` for sample format

---

## Google Shopping Mock Adapter

Deterministic mock data simulating Google Shopping results.

```bash
CATALOG_SOURCE=google_shopping
```

Useful for testing aggregated product flows without API dependencies.

---

## Protocol Adapters (Layer 2)

We now ship **mock-first** protocol adapters for readiness scoring and discovery simulation:

| Adapter | Status | Description |
|---------|--------|-------------|
| **UCP** | ✅ Mock | Business profile validation + capability intersection + readiness issues |
| **ACP** | ✅ Mock | Feed readiness + freshness + checkout/payment readiness issues |

These adapters are used in the Simulation Sandbox “Protocol readiness” panel and history badges.
See [docs/roadmap-protocol-layer.md](./roadmap-protocol-layer.md) for next steps.

## Future Adapters

| Planned | Description |
|---------|-------------|
| **Amazon** | Amazon Product Advertising API |
| **Direct API** | Generic REST/GraphQL product APIs |

---

## Data Pipeline

All adapters feed into the same pipeline:

```
External Source → RawOffer → RawProduct → Product → Product with IntentionalityProfile
                     ↓
              Confidence Score
              Completeness Score
              Inferred Fields List
```

This metadata enables alignment scoring to reason about data quality—the system can express confidence in product-intent matches based on data completeness.

See [docs/feed_schema.md](./feed_schema.md) for the complete schema specification.
