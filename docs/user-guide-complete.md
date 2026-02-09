# User Guide (Current Features Only)

This guide documents what is implemented now. Any future item is marked **Planned (not built)**.

---

## 1) Product Promise (Current)

The app helps teams improve product discoverability in LLM-driven shopping contexts by:
- inferring intent,
- scoring alignment,
- surfacing evidence and gaps,
- testing copy in simulation and experiments,
- and validating lab outcomes with observed data.

Important: experiment/simulation metrics are **lab signals**, not guaranteed production rankings.

---

## 2) Navigation and Page Order

Sidebar workflow order:
1. New Chat
2. Alignment
3. Evidence
4. Simulation
5. Experiments
6. Overview
7. Admin (separated as operational/onboarding area)

---

## 3) Experiments Module (Step by Step)

### Step 1 — Query Battery Builder
- Create a battery (name, purpose, generation mode).
- Pick generation mode:
  - `Bottom-up`
  - `Top-down`
  - `Hybrid`
- Optional: LLM-assisted generation.
- Optional seeds:
  - seed queries
  - seed features
  - seed use-cases

### Step 2 — Generate queries
- System generates candidate queries.
- Validation runs before save.
- Result includes accepted queries and rejected reasons.
- If category confidence is low for bottom-up, generation is blocked with a clarification prompt.
- Inspect generated query list.
- Enable/disable/edit weights.
- Save battery.

### Step 3 — Create experiment
- Select battery.
- Define hypothesis JSON.
- Create experiment record.

### Step 4 — Add variants (4 supported paths)
You can create experiment variants in any of these ways:
1. Manual authoring:
- Add control + candidate variants directly in the form.
2. Prefill from simulation revision:
- Pull optimized copy from simulation revisions for the same product.
3. Generate from loop evidence:
- Generate candidates from experiment + simulation + validation evidence.
- Reliability weighting is explicit: `validation > experiment > simulation`.
4. Generate cold-start copy:
- Use when historical loop evidence is weak or unavailable.
- Choose strategy:
  - `bottom_up` (features/use-cases first)
  - `top_down` (user goals/positioning first)
  - `both` (blended; recommended)

Once a candidate is selected, you can:
- apply it to the variant form, or
- create it directly with one click (`Create variant from selected loop candidate`).

### Step 5 — Run experiment
- Execute runs over battery queries.
- Metrics displayed include win-rate signals.
- Robust metrics and consensus fields appear when configured.

### Step 6 — Validate
- Log observed results (observed reality signal form).
- Track prediction accuracy.
- Pattern insights unlock when thresholds are met.

### Step 7 — Iterate in closed loop
- Review outcomes, recommendations, and validation agreement.
- Generate next variants from updated evidence.
- Continue until observed validation confidence is strong enough for decisioning.

---

## 4) Lab vs Manual Mode (Experiments)

- **Lab mode**: optimized for structured, step-by-step experiment workflow.
- **Manual mode**: controlled operation where user drives each step directly.

Tooltips in UI explain both modes on hover (separately for each toggle).

---

## 5) Simulation Module (Current Behavior)

1. Run simulation for current intent.
2. System can identify best-matching product.
3. Product selection now auto-updates to best match after run (while still allowing manual selection).
4. Optimize copy and retest.
5. Save lessons.

---

## 6) Query Generation Rules (Current)

Bottom-up generation is constrained to improve objectivity:
- avoids raw product description injection in bottom-up LLM pass,
- uses canonical intent spec + seed context,
- blocks banned terms (brand/product/model tokens),
- rejects over-specific query patterns,
- applies retry with stricter bans if acceptance is too low.

Memory reuse is quality-gated:
- low-confidence beliefs/archetypes are excluded,
- simulation lessons are excluded from LLM memory until confidence scoring is available.

---

## 7) Admin Onboarding Workspace

The Admin page now includes a step-ordered onboarding flow:
1. Client profile
2. Brand setup
3. Product catalog
4. Canonical intent spec
5. Review

Canonical intent spec fields currently captured:
- category
- sub-category
- use-cases
- audience archetypes
- feature concepts
- core constraints
- must-not-target
- objective keywords
- banned keywords

Agent skills are in a separate operational controls section.

Model gateway (operational controls):
- Add **chat/generation** and **validation** keys per provider (BYOK).
- Choose active provider + model for chat; validation can use a separate model.
- Activating a provider updates `.env.local` and refreshes the backend runtime.

Canonical intent spec editor also supports:
- **Preview UCP/ACP autofill** (no save).
- **Apply autofill** (writes canonical spec + raw/normalized/mapping metadata).

---

## 8) Validation Signals (Current)

Currently implemented:
1. **Synthetic validation signal** via Validation Jobs (in-app BYOK or external paste-back).
2. **Observed reality signal** via manual observed validation logging.
3. External analytics events via API ingestion.

Validation page (current):
- Select entity (experiment, simulation, or battery).
- Choose provider (OpenAI, Gemini, Claude, OpenRouter) and mode (in-app/external).
- In-app runs immediately via BYOK; external requires structured JSON paste-back.
- Results stored with raw output + structured result.

Interpretation rule:
- Synthetic validation signal is a fast screening signal.
- Observed reality signal is the grounding signal for real performance decisions.

**Planned (not built):**
- native GA4 connector with direct mapping flow.

---

## 9) Deployment Snapshot

Current:
- Backend on Python runtime.
- Frontend on Vercel.

Planned:
- Full Vercel backend runtime deployment after serverless + DB adaptations.

See `docs/deployment.md` for commands and environment setup.

---

## 10) Troubleshooting Quick Checks

- If battery output is weak, verify canonical spec fields are populated.
- If bottom-up quality is poor for new clients, add seed features/use-cases.
- If generation is blocked, use the clarification prompt to set category in canonical spec.
- If insights are locked, check validation count/accuracy.
- If admin changes do not appear, verify active client/brand/product context.
- If loop generation is weak early, use cold-start copy generation first, then transition to loop evidence generation after runs/validations accumulate.
