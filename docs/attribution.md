# Attribution Loop

- `IntentEvent` records each detected intent (user_id, platform, label).
- `RecommendationEvent` captures product IDs, empowering scores, and clarifications.
- `ConversionEvent` (placeholder) can be recorded when downstream signals confirm
  a purchase; link it to a recommendation event via `recommendation_event_id`.

Use `python -m attribution.ga4_export ga4_events.json` to export events for
inspection or GA4 ingestion.
