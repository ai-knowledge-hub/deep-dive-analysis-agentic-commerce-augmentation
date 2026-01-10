# Evaluation Harness

The evaluation layer captures the “representation A/B tests” described in the
research. It contains:

- Canonical shopping intent queries (`queries/shopping_intents.json`)
- Simulators that replay intents against different product representations
- Metrics for inclusion rate, empowerment alignment, and description fidelity

This folder is currently scaffolded so we can plug metrics in once the Shopify
adapter feeds live data into the core transformers.
