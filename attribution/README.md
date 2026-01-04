# Attribution Layer

This package captures events emitted by LLM-mediated shopping flows. It
introduces:

- Deterministic event schemas (conversation start, recommendation surfaced,
  commerce conversion)
- Referrer detection helpers to attribute conversions back to Gemini/GPT/Perplexity
  surfaces
- Export hooks for GA4/Looker or custom dashboards

Future work will connect these models to webhook receivers so empowerment-driven
recommendations can be measured alongside traditional conversion metrics.
