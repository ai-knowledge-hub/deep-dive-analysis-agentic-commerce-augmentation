# Commerce Adapters

The platform loads products via adapters that transform external catalog formats into our empowerment-aware product model. Each adapter emits `RawOffer` objects that flow through the `RawOffer → RawProduct → Product` pipeline.

## Available Adapters

| Adapter | Source | Confidence | Use Case |
|---------|--------|------------|----------|
| `mock` | Built-in test data | High | Development, testing |
| `shopify` | Shopify Storefront API | High | First-party merchant data |
| `google_shopping` | Mock Google Shopping | Medium | Testing aggregated flows |
| `google_merchant` | Merchant Center JSON feed | Medium | Production aggregated data |

---

## Mock Adapter

For local development and testing.

```bash
# .env.local
CATALOG_SOURCE=mock
```

No additional configuration required. Returns deterministic product data for consistent testing.

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
- Empowerment scoring considers data uncertainty
- See `data/google_merchant_feed.json` for sample format

---

## Google Shopping Mock Adapter

Deterministic mock data simulating Google Shopping results.

```bash
CATALOG_SOURCE=google_shopping
```

Useful for testing aggregated product flows without API dependencies.

---

## Future Adapters

The architecture supports additional adapters:

| Planned | Description |
|---------|-------------|
| **UCP** | Google Universal Commerce Protocol integration |
| **ACP** | OpenAI Agentic Commerce Protocol integration |
| **Amazon** | Amazon Product Advertising API |
| **Direct API** | Generic REST/GraphQL product APIs |

See [docs/strategic-positioning.md](./strategic-positioning.md) for UCP adapter design.

---

## Data Pipeline

All adapters feed into the same pipeline:

```
External Source → RawOffer → RawProduct → Product
                     ↓
              Confidence Score
              Completeness Score
              Inferred Fields List
```

This metadata enables empowerment scoring to reason about data quality—agents can express uncertainty ("this is a strong candidate" vs. "this is a hunch").

See [docs/feed_schema.md](./feed_schema.md) for the complete schema specification.
