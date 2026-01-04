# Empowerment Metrics: The Dual Dashboard

## Overview

If you only measure CTR, you can only build CTR machines.

This document specifies the **dual dashboard**—two sets of metrics, tracked side by side, both real. Neither set is optional. Neither is more real than the other.

The point isn't moral purity. The point is **seeing the full picture** so you can avoid building a system that optimizes society into a corner.

---

## The Two Dashboards

### Performance Metrics (What We've Always Measured)

These are legitimate business metrics. They're not evil. They're incomplete.

| Metric | Description | Measurement |
|--------|-------------|-------------|
| **Conversions** | Did the user complete the intended action? | Binary or count |
| **Revenue** | Transaction value generated | Currency |
| **Cost per Acquisition** | Efficiency of customer acquisition | Currency per conversion |
| **Return on Ad Spend** | Revenue generated per dollar spent | Ratio |
| **Engagement** | Interaction depth and duration | Time, clicks, actions |

### Agency Metrics (What We Should Have Been Measuring)

These metrics ensure the system serves human flourishing, not just business outcomes.

| Metric | Description | Measurement |
|--------|-------------|-------------|
| **Goal Consistency** | Are outcomes aligned with user-declared goals? | Score 0.0-1.0 |
| **Exploration Diversity** | Is the user seeing varied options or being funneled? | Entropy measure |
| **Regret Proxy** | Returns, negative feedback, blocks, rapid churn | Inverse signal |
| **Trust Proxy** | Repeat usage, reduced ad blocking, positive sentiment, referrals | Composite score |
| **Autonomy Preservation** | Can the user easily disengage, change mind, say no? | Checklist score |
| **Capability Growth** | Is the user becoming more capable over time? | Longitudinal measure |

---

## Detailed Metric Definitions

### Goal Consistency Score

**What it measures:** Whether recommendations and outcomes align with what the user said they wanted to achieve.

**Implementation:** `src/empowerment/goal_alignment.py`

```python
class GoalAlignmentResult:
    score: float           # 0.0 (no alignment) to 1.0 (perfect alignment)
    matched_goals: List[str]
    reasoning: str         # Human-readable explanation
```

**Calculation:**
1. Compare recommendation attributes to user's declared goals
2. Weight by goal importance (from semantic memory)
3. Penalize recommendations that serve unstated commercial objectives

**Warning threshold:** < 0.5 triggers review

---

### Exploration Diversity Index

**What it measures:** Whether the system is expanding or narrowing the user's option space.

**Formula:** Shannon entropy over recommendation categories

```
H = -Σ p(category) × log₂(p(category))
```

**Interpretation:**
- High entropy = diverse options presented
- Low entropy = filter bubble forming

**Warning threshold:** Entropy dropping over 3+ sessions

---

### Regret Proxy Signals

**What it measures:** Post-decision indicators that the user wishes they'd chosen differently.

| Signal | Weight | Detection |
|--------|--------|-----------|
| Product return | High | Transaction reversal |
| Subscription cancellation | High | Within 30 days |
| Negative feedback | Medium | Explicit rating < 3/5 |
| Advertiser block | Medium | User action |
| Support complaint | Medium | Ticket analysis |
| Rapid churn | Low | Session < 30s after action |

**Aggregation:** Weighted sum, normalized to 0.0-1.0 (higher = more regret)

**Warning threshold:** > 0.3 triggers recommendation review

---

### Trust Proxy Signals

**What it measures:** Indicators that the user trusts and values the system.

| Signal | Weight | Detection |
|--------|--------|-----------|
| Return visits | High | Session frequency |
| Voluntary engagement | High | Unprompted interactions |
| Referrals | High | Attribution tracking |
| Positive feedback | Medium | Explicit rating > 4/5 |
| Feature adoption | Medium | New feature usage |
| Ad blocker disabled | Low | Technical detection |

**Aggregation:** Weighted sum, normalized to 0.0-1.0 (higher = more trust)

**Target:** > 0.6 and increasing over time

---

### Physical Agency

**What it measures:** Whether recommendations support bodily autonomy and health.

| Factor | Description |
|--------|-------------|
| Posture support | Does the product/service support healthy posture? |
| Ergonomic design | Is it designed for sustainable use? |
| Fatigue consideration | Does it account for user energy levels? |
| Health alignment | Does it align with stated health goals? |

**Implementation:** `src/empowerment/schemas.py`

---

### Cognitive Relief

**What it measures:** Whether the system reduces or increases mental burden.

| Factor | Description |
|--------|-------------|
| Decision simplification | Are choices presented clearly? |
| Overwhelm reduction | Is the user showing signs of decision fatigue? |
| Confusion elimination | Does the user understand their options? |
| Cognitive load | How much mental effort is required? |

**Detection signals:**
- Long dwell time without action = possible confusion
- Rapid switching between options = possible overwhelm
- Explicit "I don't understand" signals

**Implementation:** `src/empowerment/alienation.py` (detects "overwhelmed" and "confused" states)

---

### Wellbeing Alignment

**What it measures:** Whether recommendations promote sustainable, flourishing-oriented outcomes.

| Factor | Description |
|--------|-------------|
| Sustainable habits | Does this support long-term wellbeing? |
| Value alignment | Does this align with user's stated values? |
| Balance promotion | Does this support life balance? |
| Growth orientation | Does this support capability development? |

---

## The Dual Dashboard Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DUAL DASHBOARD                                │
├─────────────────────────────┬───────────────────────────────────────┤
│     PERFORMANCE             │           AGENCY                       │
├─────────────────────────────┼───────────────────────────────────────┤
│ Conversions:     127        │ Goal Consistency:     0.73 ████████░░ │
│ Revenue:         $4,230     │ Exploration Index:    0.81 █████████░ │
│ CPA:             $12.40     │ Regret Proxy:         0.12 ██░░░░░░░░ │
│ ROAS:            3.2x       │ Trust Proxy:          0.68 ███████░░░ │
│ Engagement:      4.2 min    │ Autonomy Score:       0.85 █████████░ │
├─────────────────────────────┴───────────────────────────────────────┤
│ COMBINED HEALTH: ████████░░ (Good)                                   │
│                                                                      │
│ ⚠️  Warning: Exploration Index dropped 0.08 this week               │
│ ✓  Trust Proxy increased 0.05 (referrals up)                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Decision Rules

### When Metrics Conflict

If performance is high but agency is low:
1. **Do not celebrate.** This is extraction, not service.
2. Review constraint checks—something may have slipped through.
3. Investigate regret signals—delayed negative effects incoming.

If agency is high but performance is low:
1. **This is acceptable short-term.** Trust compounds.
2. Review if goals are being served—maybe commercial action isn't needed.
3. Consider if the product/service actually fits the user's goals.

### Minimum Thresholds

| Metric | Minimum | Action if Below |
|--------|---------|-----------------|
| Goal Consistency | 0.4 | Block recommendation |
| Exploration Index | 0.3 | Force diversity injection |
| Regret Proxy | 0.5 (inverse) | Review and pause |
| Trust Proxy | 0.3 | Investigate and remediate |

---

## Implementation Mapping

| Metric | Primary Implementation |
|--------|----------------------|
| Goal Consistency | `src/empowerment/goal_alignment.py` |
| Exploration Diversity | `src/empowerment/optimizer.py` |
| Regret Proxy | `src/empowerment/reflection.py` |
| Trust Proxy | `src/memory/episodic.py` |
| Physical Agency | `src/empowerment/schemas.py` |
| Cognitive Relief | `src/empowerment/alienation.py` |
| Wellbeing Alignment | `src/empowerment/schemas.py` |

---

## References

- [The Empowerment Imperative](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing) — "The Metrics That Actually Matter" section
- [agency-layer.md](./agency-layer.md) — Guardrail 4: Dual Reward Signal
- [architecture.md](./architecture.md) — System architecture overview

---

**Neither dashboard is optional. Neither is more real than the other. Both must be green for the system to be healthy.**
