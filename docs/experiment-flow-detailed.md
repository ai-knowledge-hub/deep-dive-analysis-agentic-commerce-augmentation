# Experiment Flow (Detailed)

This document explains the full experiment flow in operational detail, including how variants are generated, how trust is built, and how users should interpret outputs.

---

## 1) Goal and Trust Model

The Experiments flow is designed for **decision support**, not guaranteed ranking prediction.

Trust is built through:
- explicit workflow stages (battery -> variants -> runs -> metrics -> validation),
- source transparency (where each variant candidate came from),
- reliability weighting in loop generation (`validation > experiment > simulation`),
- and observed reality checks in the Validation module.

---

## 2) End-to-End Flow

1. Build query battery.
2. Generate and review queries.
3. Create experiment.
4. Create variants (manual, simulation prefill, loop evidence, or cold-start).
5. Run experiment across battery queries.
6. Review run outcomes and aggregate metrics.
7. Validate results (synthetic and observed).
8. Generate next variants from updated evidence.

The system is intentionally iterative: each cycle should produce better-grounded hypotheses.

---

## 3) Variant Creation Paths

### A) Manual authoring
Use when the team already has a clear hypothesis and proposed copy.

### B) Prefill from simulation revision
Use when Simulation already produced a good copy revision for the same product.
- Pulls candidate description and metadata into the variant form.
- Useful for rapidly moving simulation insights into controlled experiments.

### C) Generate from loop evidence
Use when prior experiment/simulation/validation history exists.
- Endpoint: `POST /experiments/{experiment_id}/variants/generate`
- Request mode: `mode="loop_evidence"`
- Candidate generation is based on:
  - experiment variants/metrics/runs,
  - linked simulation gap signals,
  - copy revisions (simulation + experiment),
  - logged validations.
- Reliability hierarchy is enforced:
  - validation evidence (highest),
  - experiment evidence,
  - simulation evidence.

### D) Generate cold-start copy
Use when historical evidence is missing or too thin.
- Endpoint: `POST /experiments/{experiment_id}/variants/generate`
- Request mode: `mode="cold_start"`
- Strategy options:
  - `bottom_up`: start from concrete features/use-cases.
  - `top_down`: start from user outcomes/positioning.
  - `both`: blend both approaches (recommended default).
- Policy:
  - brand and metadata mentions are allowed,
  - factual grounding is still required,
  - candidates must align to inferred user intent/needs/goals.

---

## 4) Candidate-to-Variant Actions

After generation, users can:
- select a candidate and apply it to the form (`Use selected loop candidate`), or
- skip form editing and create immediately (`Create variant from selected loop candidate`).

This supports both cautious review and fast execution.

---

## 5) What the User Should Check Before Running

Before clicking run:
- label clarity (control vs candidate),
- copy description quality and factuality,
- payload metadata (`source_type`, confidence/strategy fields),
- query battery quality (enabled queries and weights),
- experiment context (correct product/client scope).

---

## 6) How to Interpret Results Safely

- Experiment metrics are lab signals.
- Synthetic validation is a fast screening signal.
- Observed validation is the grounding signal for production confidence.

Recommended interpretation order:
1. Check metric direction and effect size.
2. Check consistency across runs/queries.
3. Check synthetic-vs-observed agreement.
4. Prefer decisions with stronger observed validation support.

---

## 7) Recommended Operating Pattern

For new products:
1. Start with `cold_start` generation (`both` strategy).
2. Run experiments and collect metrics.
3. Log validation observations.
4. Shift to `loop_evidence` generation once evidence accumulates.
5. Continue iteration until observed validation is stable.

For mature products:
1. Default to `loop_evidence` generation.
2. Use cold-start only when launching a new audience/use-case with sparse history.

---

## 8) Failure and Fallback Behavior

- If model output is missing or invalid JSON, fallback candidates are generated.
- Fallback candidates are explicitly marked by response field `used_fallback=true`.
- Users should treat fallback output as lower-confidence and validate quickly via runs/observations.

---

## 9) API Contract (Generation)

`POST /experiments/{experiment_id}/variants/generate`

Request fields:
- `max_candidates` (1..5)
- `mode`: `loop_evidence` | `cold_start`
- `strategy`: `bottom_up` | `top_down` | `both`
- `client_id`, `user_id`

Response highlights:
- `generation_mode`
- `generation_strategy`
- `summary`
- `evidence`
- `candidates[]` (`label`, `description`, `rationale`, `payload`, `confidence`)
- `used_fallback`

---

## 10) Why This Flow Is Trustworthy

The flow is trustworthy when used as intended because it:
- keeps provenance visible,
- separates fast synthetic screening from observed grounding,
- enforces evidence weighting,
- and supports explicit human review before and after execution.

Use this module as a transparent experimentation system, not an oracle.
