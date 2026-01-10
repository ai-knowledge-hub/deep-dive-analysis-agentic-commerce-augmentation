# The Agency Layer: Technical Specification

## Overview

If you build agentic marketing without guardrails, you default to [World A](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing). Not because you're evil—because that's where the local gradient points.

This document specifies the **minimal layer** that changes the trajectory from extraction to empowerment.

---

## The Four Guardrails

### 1. Explicit Goals (Not Inferred "Interests")

**Problem:** The current paradigm infers what you want from what you do. Click on running shoes, get more running shoe ads. But what you click on and what you actually want are often different.

**Solution:** Don't just infer from behavior. Ask. Let users declare what they're actually trying to achieve.

#### Implementation in This Repo

| Component | Location | Behavior |
|-----------|----------|----------|
| Intent Classifier | `modules/intent/classifier.py` | Classifies user intent into goal-oriented categories |
| Intent Taxonomy | `modules/intent/taxonomy.py` | Defines explicit goal types (learning, health, career, etc.) |
| Semantic Memory | `modules/memory/semantic.py` | Stores long-term goals and values |
| Goal Alignment | `modules/empowerment/goal_alignment.py` | Scores recommendations against declared goals |

#### Interface Contract

```python
# Goals are explicit, not inferred
class UserGoal:
    goal_type: str        # e.g., "skill_acquisition", "health_improvement"
    description: str      # User's own words
    target_capability: str
    timeline: str         # Optional: "3_months", "1_year"

# Recommendations reference goals explicitly
class Recommendation:
    product: Product
    goal_alignment_score: float  # 0.0 - 1.0
    alignment_reasoning: str     # Human-readable explanation
```

#### Invariant

> Commerce is always downstream of clarified human goals.

---

### 2. Consent Gates (Before Personalization)

**Problem:** The current paradigm personalizes by default. You have to actively opt out, if you can find the setting.

**Solution:** Personalization is off until you turn it on. When you do, you know what you're turning on.

#### Implementation in This Repo

| Component | Location | Behavior |
|-----------|----------|----------|
| Working Memory | `modules/memory/working.py` | Session-scoped only; no persistence without consent |
| Episodic Memory | `modules/memory/episodic.py` | Reflections stored only after explicit action |
| MCP Tools | `modules/mcp/tools/` | Each tool documents what data it accesses |

#### Interface Contract

```python
# Memory writes are explicit events, not silent logging
class MemoryEvent:
    event_type: str       # "goal_added", "preference_updated", "reflection_stored"
    user_consented: bool  # Must be True for persistence
    explanation: str      # What will be stored and why

# "Why am I seeing this?" always has an answer
class RecommendationExplanation:
    factors: List[str]           # What influenced this recommendation
    data_used: List[str]         # What user data was accessed
    how_to_change: str           # How to modify or disable
```

#### Invariant

> "Why am I seeing this?" has a complete, honest answer. "Stop showing me this" actually works.

---

### 3. Constraint Checks (Before Action)

**Problem:** Without hard constraints, optimization will find every loophole. "But the metrics" becomes the excuse for dark patterns.

**Solution:** Before the system takes any action, it runs through hard constraints. If the action fails any constraint, it doesn't happen. No exceptions.

#### Implementation in This Repo

| Component | Location | Behavior |
|-----------|----------|----------|
| Alienation Detector | `modules/empowerment/alienation.py` | Detects manipulation signals |
| Autonomy Guard Agent | `agents/autonomy_guard_agent.py` | Orchestrates constraint checking |
| Empowerment Optimizer | `modules/empowerment/optimizer.py` | Applies constraints before ranking |

#### Constraint Catalog

| Constraint | Description | Enforcement |
|------------|-------------|-------------|
| **No sensitive inference** | No inference of health, financial status, emotional state without explicit disclosure | Block action |
| **No escalation loops** | Frequency caps, cooldown periods between recommendations | Throttle action |
| **No dark patterns** | No artificial scarcity, disguised ads, manipulative countdown timers | Block action |
| **No vulnerability exploitation** | No targeting based on documented cognitive vulnerabilities | Block action |
| **Overwhelm detection** | Stop if user shows signs of decision fatigue | Pause and reflect |
| **Confusion detection** | Stop if user seems confused by options | Simplify and explain |

#### Interface Contract

```python
class ConstraintCheck:
    constraint_name: str
    passed: bool
    violation_details: Optional[str]
    remediation: Optional[str]  # How to fix if failed

class ActionGate:
    proposed_action: Action
    constraints_checked: List[ConstraintCheck]
    action_permitted: bool
    blocked_reason: Optional[str]
```

#### Invariant

> If the action fails any constraint, it doesn't happen. No exceptions. No "but the metrics."

---

### 4. Dual Reward Signal (Agency)

**Problem:** If you only measure CTR, you can only build CTR machines. Single-objective optimization ignores everything that matters but isn't measured.

**Solution:** The system optimizes for two reward signals: performance AND agency. Neither is optional.

#### Implementation in This Repo

| Component | Location | Behavior |
|-----------|----------|----------|
| Goal Alignment | `modules/empowerment/goal_alignment.py` | Measures goal-consistency |
| Reflection System | `modules/empowerment/reflection.py` | Captures regret signals |
| Empowerment Schemas | `modules/empowerment/schemas.py` | Defines agency metrics |
| Empowerment Optimizer | `modules/empowerment/optimizer.py` | Balances dual objectives |

#### The Dual Dashboard

See [empowerment_metrics.md](./empowerment_metrics.md) for the complete metric specification.

**Performance Signal:**
- Did the user convert?
- What was the transaction value?
- Did they complete the intended action?

**Agency Signal:**
- Was the outcome goal-consistent?
- Did the user show regret signals?
- Was exploration preserved or narrowed?
- Did trust increase or decrease?

#### Interface Contract

```python
class DualReward:
    performance_score: float      # Traditional metrics
    agency_score: float           # Empowerment metrics
    combined_score: float         # Weighted combination
    tradeoff_explanation: str     # If scores conflict, explain why

class OptimizationResult:
    selected_action: Action
    performance_expected: float
    agency_expected: float
    alternatives_considered: List[Action]
    selection_reasoning: str      # Why this action over alternatives
```

#### Invariant

> Neither performance nor agency can be zero. Both must be positive for an action to be selected.

---

## Architectural Integration

The agency layer is not a separate module bolted on top. It is woven through the architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    User Interaction                      │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
| GUARDRAIL 1: Explicit Goals                              │
│ Intent clarification before any commerce action          │
│ modules/intent/ + modules/memory/semantic.py                     │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ GUARDRAIL 2: Consent Gates                               │
│ User controls what is remembered and personalized        │
│ modules/memory/working.py + modules/memory/episodic.py           │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ GUARDRAIL 3: Constraint Checks                           │
│ Hard limits before any action executes                   │
│ modules/empowerment/alienation.py                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ GUARDRAIL 4: Dual Reward Signal                          │
│ Optimize for agency AND performance                      │
│ modules/empowerment/goal_alignment.py + optimizer.py         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Commerce Action                       │
│ Products as capability-enabling tools, not desire objects│
│ modules/commerce/                                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ MANDATORY: Reflection                                    │
│ Learning loop closure—did this actually help?            │
│ modules/empowerment/reflection.py                            │
└─────────────────────────────────────────────────────────┘
```

---

## Validation Checklist

Before any feature ships, verify:

- [ ] **Goal Explicit:** Can you trace the recommendation to a user-declared goal?
- [ ] **Consent Clear:** Did the user opt into the personalization that made this possible?
- [ ] **Constraints Passed:** Did all hard constraints pass before action?
- [ ] **Dual Score Positive:** Are both performance and agency scores positive?
- [ ] **Explanation Available:** Can you explain "why this?" in human-readable terms?
- [ ] **Reflection Scheduled:** Is there a mechanism to learn if this actually helped?

If any answer is "no," the feature is not ready.

---

## References

- [The Empowerment Imperative](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing) — Source of the four guardrails framework
- [architecture.md](./architecture.md) — System architecture overview
- [empowerment_metrics.md](./empowerment_metrics.md) — Detailed metric definitions

---

**The agency layer is the smallest intervention that changes the trajectory.**
