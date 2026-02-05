# App Workflows (Current + Planned)

This is the operational workflow map for the current codebase.
Anything not implemented is explicitly labeled **Planned (not built)**.

---

## 1) Workflow Graph

```
Chat
  → Alignment
    → Evidence
      → Simulation (optimize + retest + lessons)
  → Experiments
      → Query Battery Builder
      → Variants
      → Run + Metrics
      → Validation Logging
      → Prediction Accuracy + Unlock status

Admin Onboarding
  → Client
  → Brand
  → Product
  → Canonical Intent Spec
  → Review
```

---

## 2) Manual Workflow (Chat-first)

1. User starts in Chat.
2. System infers intent + clarifies goal.
3. Alignment ranks candidate products.
4. Evidence explains wins/gaps.
5. Simulation runs scenario and can optimize copy.
6. Retest confirms lab delta; lesson is stored.

Current outputs:
- intent/goals
- alignment breakdown
- evidence signals
- simulation scores + protocol readiness
- lesson snapshots

---

## 3) Experiment Workflow (Lab Mode)

1. Create/select a query battery.
2. Generate queries (top-down, bottom-up, or hybrid; optional LLM-assisted).
3. Review generated queries and rejection reasons.
4. Create experiment and add variants.
5. Run experiment.
6. Read metrics (win rate, robust win rate, evidence strength/consensus when available).
7. Log validations and monitor prediction accuracy.

Current safeguards:
- Query filtering before persistence.
- Soft-gated pattern insights until validation thresholds are met.
- Lab result messaging that requires real-world validation.

---

## 4) Query Battery Builder Workflow (Current)

### Inputs
- Battery metadata
- Seed queries (optional)
- Seed features/use-cases (optional; useful for bottom-up)
- Product metadata + canonical intent spec
- LLM-assist toggle

### Processing
1. Build capsule context.
2. Generate deterministic base queries by selected mode.
3. Optionally add LLM-generated queries.
4. Deduplicate + validate.
5. Retry once with stricter banned terms if acceptance is low.

### Review surface
- Accepted queries are saved to battery.
- Rejected queries are surfaced with reasons (for manual correction/approval flow).

---

## 5) Validation Workflow (Current)

Validation sources implemented:
1. Manual verification entries per experiment.
2. External analytics events via `/analytics/events`.

Metrics computed:
- verified runs
- prediction accuracy
- unlock status for insights

Soft-gate rule:
- unlock only when `>=10` verified and `>=75%` accuracy.

---

## 6) Admin Onboarding Workflow (Current)

The Admin page is now step-ordered and collapsible:

1. **Client profile**: select/create client, add client users.
2. **Brand setup**: select/create brand under active client.
3. **Product catalog**: select/create product; edit platform profile section.
4. **Canonical intent spec**: controlled ontology-driven fields.
5. **Review**: completion status of onboarding requirements.

Operational controls (agent skills) are separated from onboarding fields.

---

## 7) Self-Learning Workflow (Current vs Planned)

### Current
- Simulation lessons are stored and retrievable.
- Brand beliefs are generated from experiment outcomes.
- Query generation can reuse high-confidence beliefs and archetypes.

### Planned (not built)
- Cross-run distillation into reusable heuristics by vertical/domain.
- Confidence scoring for simulation lessons before memory reuse.
- Automatic weekly ontology/synonym updates from failures.

---

## 8) Deployment Workflow

Current supported path:
- Backend: Python runtime (FastAPI)
- Frontend: Vercel (Next.js)

Planned (not built):
- Full backend on Vercel Python runtime with production-grade external DB and serverless adaptations.

