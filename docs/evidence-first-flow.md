# Evidence-First Flow - Current Implementation

**Date:** 2026-01-29  
**Status:** ✅ Complete & Polished  
**Purpose:** Evidence discovery + explanation panels that feed Simulation decisions

---

## Overview

The Evidence-First Flow is a **focused analysis layer**:
- It **explains** why open‑web winners rank for the inferred intent.
- It **compares** our product copy to winning signals.
- It **recommends** the next action and sends users to Simulation.

It sits inside the **Automated Lab** narrative as a supporting step before optimization.

---

## What’s Built (Current)

### EvidenceCard.tsx
**Location:** `web/components/evidence/EvidenceCard.tsx`

**Features:**
- Rank badge
- **Alignment score** badge (ALIGN)
- Summary + source + link
- “Why they win” snippet
- Top signal chips

---

### EvidencePanel.tsx
**Location:** `web/components/evidence/EvidencePanel.tsx`

**Tabs:**
1. **Evidence** — open‑web results ranked by alignment score
2. **Explanation** — score distribution + why‑they‑win + signal deltas + 3‑path signal model
3. **Next actions** — counterfactual lift + CTA to Simulation

**Key UX:**
- Empty state when no chat data exists
- Clean grid layout
- Minimal, readable signal chips

---

## Data Source

Evidence is **always derived from the latest chat session**.

Loading behavior:
1. Read from `localStorage` cache  
2. If missing, hydrate from latest session snapshot  
3. Render into Evidence tabs

---

## User Workflow

1. **Run a chat query**
2. Open **Evidence** page
3. **Evidence tab** → see ranked open‑web results  
4. **Explanation tab** → see why winners win + signal deltas  
5. **Next actions tab** → counterfactual lift + open Simulation

---

## Signal Model (3‑Path)

Signals are computed via three paths:

1. **Intent/Goal signals (top‑down)**  
   - From inferred goals + constraints  
   - Weight = intent confidence × explicitness

2. **Evidence signals (bottom‑up)**  
   - From recurring features across winners  
   - Weight = frequency among winners × alignment score

3. **Copy presence signals (our product)**  
   - From our copy vs those two sets  
   - Weight = coverage + missing penalties

Specificity vs breadth = ratio of intent signals to evidence signals.

---

## How to Interpret the Signals

**Intent signals (top‑down)**  
These are directly tied to the inferred user intent (size, budget, constraints).  
If these are missing in your copy, your product will **not surface** for that intent.

**Evidence signals (bottom‑up)**  
These are patterns repeated across winning products.  
If these are missing, you may appear but **rank lower** than competitors.

**Copy‑presence signals (our product)**  
These show which intent/evidence signals your copy already contains.  
More coverage = higher alignment; missing items = gap analysis inputs.

**Specificity vs breadth**  
High specificity = stronger fit for a narrow intent.  
Higher breadth = more discoverable across adjacent intents.  
Use Simulation to shift the balance based on your goals.

---

## Known Limitations

- No filtering/sorting yet
- No export yet
- Charts are static (no drill‑down)

---

## Next Enhancements (Optional)

- Filter evidence by source / alignment threshold
- Export evidence + signals to CSV
- Add interactive score distribution chart

---

## API Reference (Future)

When wired directly to backend:

### POST /evidence/analyze
```json
{
  "query": "TV for bright room",
  "max_items": 5,
  "user_id": "user_123",
  "client_id": "client_abc"
}
```

**Response:**
```json
{
  "goals": ["Find TV that works in bright rooms"],
  "evidence_products": [
    {
      "id": "tv-bright-01",
      "name": "Aurora QLED 65",
      "description": "65-inch 4K QLED TV...",
      "source_url": "https://..."
    }
  ]
}
```
