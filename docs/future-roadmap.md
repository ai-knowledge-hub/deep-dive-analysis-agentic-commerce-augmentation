# Future Roadmap (Deferred Features + Enterprise Extensions)

**Purpose:** Track features we intentionally defer during the hackathon/MVP phase so stakeholders know what’s planned, what’s not, and why.

This document complements:
- `docs/roadmap-protocol-layer.md` (protocol simulation milestones)
- `docs/build-plan.md` (execution phases)
- `docs/product-workflow.md` (current user flow)

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

**Current:** No post‑purchase tracking.

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

## 8) Agentic Loop Extensions (Deferred)

1. **Full agent loop orchestration**
2. **Active learning from “lessons learned”**
3. **Knowledge graph & ontology‑based reasoning**

---

## 9) Infra + Scalability (Deferred)

1. **Postgres + row‑level tenancy**
2. **Queue + worker system**
3. **Schema registry with caching**
4. **Search index integration**

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
