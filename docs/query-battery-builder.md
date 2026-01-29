Structured prediction of the expected change.

Example:
> If we frame “3000 nits” as “anti‑glare for bright rooms”, then win‑rate on the “bright room TV” battery increases.

---

## 3) Data Model (DB tables)

We already have `clients/brands/products/simulation_runs/simulation_lessons`.
Add the following tables (names are suggested; IDs are UUIDs unless noted).

### `query_batteries`
- `id`
- `client_id` (required)
- `brand_id` (nullable)
- `product_id` (required)
- `name`
- `purpose` (text)
- `generation_mode` (`bottom_up|top_down|hybrid`)
- `status` (`draft|active|archived`)
- `created_at`, `updated_at`

### `query_battery_queries`
- `id`
- `battery_id` (fk)
- `query_text`
- `query_type` (`coverage|market|adversarial|protocol`)
- `intent_archetype` (nullable string)
- `constraints_json` (nullable json) — e.g. `{ price_max, delivery_by, availability_required }`
- `weight` (float default `1.0`)
- `enabled` (bool)
- `created_at`

### `experiments`
- `id`
- `client_id` (required)
- `brand_id` (nullable)
- `product_id` (required)
- `battery_id` (fk)
- `name`
- `hypothesis_json` (json)
- `competitor_policy_json` (json) — how competitors are selected/held constant
- `status` (`draft|running|completed|archived`)
- `created_at`, `updated_at`

### `experiment_variants`
- `id`
- `experiment_id` (fk)
- `label` (`baseline|A|B|C|…`)
- `type` (`copy|tone|protocol|mixed`)
- `payload_json` (json) — copy/tone/protocol changes
- `created_at`

### `experiment_runs`
- `id`
- `experiment_id` (fk)
- `variant_id` (fk to `experiment_variants`)
- `query_id` (fk to `query_battery_queries`)
- `simulation_run_id` (fk to existing `simulation_runs`)
- `created_at`

### `experiment_metrics`
- `id`
- `experiment_id` (fk)
- `variant_id` (fk)
- `metrics_json` (json) — aggregated metrics snapshot
- `created_at`

---

## 4) Battery Generation (v1)

### Bottom‑up generator (product → intents → queries)
Inputs:
- product description + intentionality profile + metadata (UCP/ACP readiness issues)

Outputs:
- 10–30 queries labeled `coverage` and `protocol`

### Top‑down generator (market → queries)
Inputs:
- user-pasted query list (v1)

Outputs:
- deduped queries labeled `market`

### Adversarial generator
Inputs:
- competitor products and/or competitor brand list

Outputs:
- comparison queries labeled `adversarial`

---

## 5) API (proposed)

### Batteries
- `POST /batteries`
  - `{ client_id, product_id, brand_id?, name, purpose?, generation_mode }`
- `POST /batteries/{battery_id}/generate`
  - `{ source: "bottom_up"|"top_down"|"hybrid", seed_queries?: string[], limit?: number }`
- `GET /batteries?client_id=...&product_id=...`
- `GET /batteries/{battery_id}`
- `PATCH /batteries/{battery_id}`
- `POST /batteries/{battery_id}/queries`
- `PATCH /batteries/{battery_id}/queries/{query_id}`

### Experiments + variants
- `POST /experiments`
  - `{ client_id, product_id, brand_id?, battery_id, name, hypothesis_json, competitor_policy_json? }`
- `POST /experiments/{experiment_id}/variants`
  - `{ label, type, payload_json }`
- `POST /experiments/{experiment_id}/run`
  - `{ variant_id }` (runs the entire battery for that variant)
- `GET /experiments?client_id=...&product_id=...`
- `GET /experiments/{experiment_id}` (includes metrics + per-query outcomes)

---

## 6) How it plugs into Simulation (v1)

For each query in a battery:
- Call existing `POST /simulation/run`
  - with `query = query_text`
  - `products = [target_variant_product + fixed competitor set]`
  - `client_id` required; `brand_id`/`product_id` optional for linkage
- Store `simulation_run_id` in `experiment_runs`
- Aggregate metrics into `experiment_metrics`

Variants:
- baseline uses the product’s current description
- variant A/B/C replaces the product description with proposed copy
- tone and protocol readiness are recorded as metadata and may be used by optimization prompts

---

## 7) UI (v1)

New page: **Experiments / Flight Tests**

1) Battery builder
- Generate (bottom-up / top-down / hybrid)
- Import market queries (paste list)
- Enable/disable, weight, edit queries

2) Experiment setup
- Hypothesis form (target metric, expected direction, rationale)
- Create variants (A/B/C) and run them

3) Results
- win-rate and mean-score per variant
- UCP readiness and ACP readiness trend per variant
- per-query table: winner, your score, delta, why-you-lost summary

---

## 8) v1 Success Criteria

- Create a battery for a product in <2 minutes.
- Run baseline across the battery.
- Create 2 variants (A/B), run them, and compare:
  - win-rate
  - mean score
  - protocol readiness (ACP/UCP)
  - top recurring gaps + lessons

