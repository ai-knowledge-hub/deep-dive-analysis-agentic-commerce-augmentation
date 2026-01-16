# Attribution Layer

The attribution module (`modules/attribution/`) captures events emitted by LLM-mediated shopping flows. It provides:

- **Deterministic event schemas** for conversation start, recommendation surfaced, and commerce conversion
- **Referrer detection** to attribute conversions back to Gemini/GPT/Perplexity surfaces
- **Export hooks** for GA4/Looker or custom dashboards

## Event Types

| Event | Description |
|-------|-------------|
| `IntentEvent` | Records detected intent (user_id, platform, label) |
| `RecommendationEvent` | Captures product IDs, empowerment scores, clarifications |
| `ConversionEvent` | Records purchase signals, linked via `recommendation_event_id` |

## Export for Analytics

Attribution events are buffered in-memory. Export them for GA4 verification:

```bash
python -m modules.attribution.ga4_export --path ga4_events.json
```

This creates a JSON payload for downstream analytics systems.

## Future Work

- Webhook receivers for real-time conversion tracking
- Empowerment-driven metrics alongside traditional conversion metrics
- Long-term outcome correlation (reflection feedback → conversion quality)

---

See [docs/empowerment_metrics.md](./empowerment_metrics.md) for how attribution feeds into the dual dashboard.
