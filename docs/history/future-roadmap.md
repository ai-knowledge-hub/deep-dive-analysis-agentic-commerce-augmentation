# Future Roadmap (Deferred Features + Enterprise Extensions)

Status: historical

**Purpose:** Track features we intentionally defer during the hackathon/MVP phase so stakeholders know what’s planned, what’s not, and why.

This document complements:
- `docs/app-architecture.md` (current + planned architecture)
- `docs/history/app-workflows.md` (historical workflows + planned extensions)

---

## 1) Protocol Layer — Full ACP/UCP Compliance (Deferred)

**Current:** Readiness scoring + mock discovery for UCP/ACP.

**Planned:**
1. **Full UCP schema bundle + strict JSON Schema validation**
   - Cache/registry of UCP schemas
   - Validate checkout/order payloads against composed schemas
2. **UCP transaction surface**
   - Checkout session creation + update + order confirmation flows
   - Webhook signature verification and retries
3. **ACP ingestion + indexing**
   - JSONL/CSV/XML/TSV ingestion pipeline
   - Feed delta updates and re-indexing
4. **ACP checkout**
   - Merchant REST endpoints and rich checkout state
5. **ACP delegated payments**
   - Token constraints, expiry, max amount
   - PSP-specific flows (Stripe delegated tokens)

---

## 2) Brand/Customer Feedback Loop (Deferred)

**Current:** Observed reality signal logging + external analytics event ingestion.

**Planned:**
1. **Feedback collection**
   - Customer feedback forms
   - Review ingestion
2. **Outcome tracking**
   - “Did this solve the intent?”
   - Outcome-based success metrics
3. **Continuous optimization**
   - Feed/test/learn loops per brand
   - Recommendations derived from feedback trends

---

## 3) Enterprise Governance & Compliance (Deferred)

1. **Audit trails + immutable logs**
2. **Role‑based access control (RBAC)**
3. **Data retention policies**
4. **SOC‑2 / ISO‑27001 readiness**
5. **Regulatory compliance toolkits**
   - GDPR/CCPA tooling
   - Consent + deletion workflows

---

## 4) Multi‑Tenant Admin Console (Deferred)

**Current:** Manual admin pickers in UI.

**Planned:**
1. **Self‑serve onboarding for clients**
2. **Brand & product management UI**
3. **Permissions + user invitations**
4. **Tenant‑scoped analytics dashboards**

---

## 5) Real‑World Verification & Observability (Deferred)

1. **Live LLM verification harness**
   - Compare predicted winners vs actual recommendations
2. **Attribution tracking**
   - Track recommendation → purchase
3. **Alerting & monitoring**
   - Discoverability regression alerts

---

## 6) Competitive Intelligence (Deferred)

1. **Competitor auto‑discovery**
2. **Share‑of‑voice tracking**
3. **Competitor capability mapping**
4. **“Why they win” dashboards**

---

## 7) Brand Voice + Authenticity (Deferred)

1. **Brand DNA model**
2. **Claim verification**
3. **Tone adherence scoring**
4. **Approval workflows for rewrites**

---

## 8) Agentic Loop Extensions (Active / Partially Implemented)

Implemented foundation:
- AgentRuntime job runner with run/action/event persistence.
- Capability registry and policy enforcement for executable runtime capabilities.
- Operator chat command surface with preflight, command receipts, and explicit retry proposals.
- Runtime worker and interval scheduler entrypoints.

Planned extensions:
1. **Command observability and structured recovery**
   - First-class timeline filtering for command receipts/outcomes (initial pass implemented)
   - Interventions entries for command-originated risky work (initial pass implemented)
   - Structured `change_plan` recovery proposals (initial pass implemented)
   - Richer retry strategies and chat outcome summaries
2. **Capability/skill registry hardening**
   - Persistent registry definitions
   - Tool input/output schema validation
   - Skill/tool version pinning on runs and actions
3. **Multi-agent roles**
   - Planner
   - Variant optimizer
   - Validation operator
   - Policy/recovery agent
4. **Active learning from “lessons learned”**
5. **Knowledge graph & ontology‑based reasoning**
6. **Scheduled experiment execution automation**
   - Automatic execution of due experiment schedules via `run_due`
   - Deployment options: cron / GitHub Action / worker service
   - Integrate with the existing loop maintenance automation template as a companion job
   - Add execution tracking for scheduled runs (start/end/status/error, run counts, affected experiment IDs)

---

## 9) Infra + Scalability (Deferred)

1. **Postgres + row‑level tenancy**
2. **Queue + worker system**
3. **Schema registry with caching**
4. **Search index integration**
5. **Unified automation runner**
   - Single scheduler for loop maintenance + experiment schedule execution
   - Shared retries, observability, and alerting for both jobs

---

## 10) UX Extensions (Deferred)

1. **Scenario templates library**
2. **Versioned simulations**
3. **Batch optimization + export**
4. **Shareable client reports**

---

## How We Decide When to Move Items Forward

| Signal | Action |
|--------|--------|
| Demand from 3+ pilot clients | Prioritize feature |
| Needed for paid deployment | Promote to P1 |
| High engineering risk | Prototype first |

---

## Next Review

This roadmap should be reviewed monthly or after each major milestone to decide what moves from **Deferred** → **Planned** → **Active**.
