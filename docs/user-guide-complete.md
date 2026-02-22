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
6. Validation
7. Overview
8. Agent runs
9. Admin (separated as operational/onboarding area)

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
- For `top_down` and `hybrid`, the generator now also derives in-context behavioral audience segments
  from recent analytics/session events and uses them to condition candidate queries.
- Step 1 now includes an **Audience segments for top-down generation** panel where you can
  enable/disable session-derived segments before generation.
- If no session-derived segments exist yet, generation falls back to canonical intent spec,
  product metadata, and stored archetypes.
- If category confidence is low for bottom-up, generation is blocked with a clarification prompt.
- Inspect generated query list.
- Enable/disable/edit weights.
- Save battery.

### Step 3 — Experiment context (auto)
- There is no required manual \"Create experiment\" action now.
- After battery + queries are ready, experiment context is initialized automatically when you start variant work.
- The protocol then tracks frozen snapshot versioning and hypothesis linkage in the background.

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
- In retrieval-backed mode, runs use a frozen protocol snapshot (`snapshot_version`) for fair comparison.
- Candidate runs are baseline-gated: control must be scored first for the active snapshot.

### Step 6 — Review outcomes and aggregate metrics
- Review the latest run winner, key metrics, and current validation state in the outcome snapshot.
- Compare variant-level win-rate and score trends before deciding next action.
- Review protocol-specific fields now shown in UI:
  - snapshot version,
  - linked hypothesis (human-readable label),
  - posterior,
  - decision action.

### Step 7 — Validate synthetic and observed results
- Open Validation from Experiments when runs exist.
- Run synthetic validation (in-app BYOK, provider run, or manual fallback) for fast screening.
- Log observed reality signals for grounding and calibration.
- Track readiness using verified count and observed accuracy thresholds.

### Step 8 — Iterate in closed loop
- Review outcomes, recommendations, and validation agreement.
- Generate next variants from updated evidence.
- Continue until observed validation confidence is strong enough for decisioning.
- Posterior-driven decisions follow:
  - `promote_variant`,
  - `iterate_variant`,
  - `reject_hypothesis`.

Implementation note:
- Decisions are produced by a versioned decision policy and stored in metrics as:
  - `decision_policy_version`
  - `decision_inputs`
  - `decision_outputs`

---

## 4) Lab vs Manual Mode (Experiments)

- **Lab mode**: optimized for structured, step-by-step experiment workflow.
- **Manual mode**: controlled operation where user drives each step directly.

Tooltips in UI explain both modes on hover (separately for each toggle).

### Agent operator mode (Current v0)

Agent operator mode is available at **Agent runs** in the sidebar.

Current behavior:
- create an agent run scoped to an experiment,
- queue proposed capability actions,
- approve/reject actions,
- execute approved actions stepwise in `auto_execute_safe` mode,
- keep execution guarded by policy checks and runtime lock/heartbeat safety.
- monitor budgets in-run (actions, variant-runs, cost) with warning states.
- inspect artifact diffs in detail (including copy diff mode).
- use timeline deep-links to jump to action, experiment, and validation contexts.

Execution modes:
- `plan_only` (default): planning + approvals only, no execution side effects.
- `auto_execute_safe`: approved actions can be executed via `step`.

Guardrails enforced before execution:
- `max_actions`
- `max_variant_runs`
- `max_cost_usd`

The Experiments page also includes an **Agent operator mode** panel with:
- latest agent run status for the selected experiment,
- direct CTAs to open/start work in Agent runs.

Reference: `docs/agentic-layer.md`.

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
1. **Synthetic validation signal** via Validation Jobs:
   - `in_app_byok` (run directly in app),
   - `provider_openai_mcp` (launch and complete in ChatGPT with callback),
   - `manual_fallback` (structured paste-back).
2. **Observed reality signal** via manual observed validation logging.
3. External analytics events via API ingestion.

Validation page (current):
- Shows a step-based Validation flow with:
  - provider defaults,
  - synthetic validation,
  - observed reality logging,
  - variant comparison,
  - decision/result summary.
- Includes a "Next recommended action" CTA and an outcome snapshot (synthetic + observed + readiness).

### Synthetic validation signal (how to use)
1. Select entity type:
   - experiment,
   - simulation,
   - query battery,
   - copy revision.
2. Select item, provider, mode, and optional model.
3. Run in one of the available modes:
   - `In-app (BYOK)`: executes immediately with configured provider/model.
   - `Provider run (ChatGPT MCP)`: starts provider run, opens provider URL, and expects signed callback completion.
   - `Manual fallback`: use structured instructions and paste back result JSON.
4. Review winner, score, evidence strength, and structured result payload.

Provider mode notes:
- `Provider run (Gemini function)` is visible in mode selection but currently backend-gated as not yet implemented.
- Provider callbacks are one-time verified tokens with TTL and replay protection.

### Observed reality signal (how to use)
Log one observed record per real-world check:
- experiment,
- variant (usually predicted winner),
- platform,
- query tested,
- observed products shown,
- observed winner variant (optional but required for accuracy scoring),
- observed position (optional),
- notes.

### Readiness and trust metrics (current logic)
- **Logged observed signals**: total observed entries.
- **Verified runs**: entries where correctness can be computed (`is_correct` known).
- **Accuracy**: `correct_runs / verified_runs`.
- **Progress**: `verified_runs / 10` (capped at 100%).
- **Unlock ready**: `verified_runs >= 10` and `accuracy >= 0.75`.

Important behavior:
- If `observed winner` is not provided, the record is logged but does not contribute to verified accuracy.
- If `observed winner` is provided and does not match the selected variant, it counts as incorrect.

### How Validation feeds the loop
- Validation summaries are used by Experiment flow to decide whether to continue testing or move to next-variant generation.
- Loop-evidence variant generation prioritizes evidence reliability as:
  - `validation > experiment > simulation`.

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
