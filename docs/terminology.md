# Terminology Glossary

This document defines the core terms used across the Agentic Commerce /
Contextual Commerce Optimization (CCO) codebase.

The goal is to ensure **conceptual precision**, prevent semantic drift,
and align research, architecture, and implementation.

---

## CCO — Contextual Commerce Optimization

**Definition**
Contextual Commerce Optimization (CCO) is an **optimization paradigm**, not a fixed platform.

CCO describes systems that:
- evaluate commerce decisions within **human context**
- ground execution in **explicitly clarified intent**
- optimize for **human outcomes**, not proxy metrics like CTR

**Key Property**
> CCO is defined by its **objective function**, not by a specific UI, stack, or deployment.

This repository represents the **first concrete implementation of CCO**.

---

## AIS — Augmented Intentionality System

**Definition**
The Augmented Intentionality System (AIS) is the **governing logic** that constrains and guides optimization.

AIS specifies:
- what kinds of influence are allowed
- how autonomy is preserved
- how learning and reflection are incorporated

**In Code**
Implemented primarily in:

```
modules/empowerment/
```

AIS replaces traditional engagement or conversion optimization.

---

## CCIA — Context-Conditioned Intent Activation

**Definition**
CCIA is a method for identifying **latent user intent** based on context,
history, and interaction signals — not just keywords.

Unlike traditional intent classification, CCIA:
- distinguishes *goals* from *queries*
- treats intent as dynamic and contextual
- feeds into downstream reasoning, not direct execution

**In Code**

```
modules/intent/
```

---

## Agentic Commerce

**Definition**
Agentic Commerce is a **runtime context** in which CCO is applied to
products, catalogs, and transactions.

In Agentic Commerce:
- users are treated as agents with goals
- products are treated as instruments
- decisions are scaffolded, not forced

Agentic Commerce is **one instantiation** of CCO (others include search,
programmatic advertising, conversational assistants).

---

## Empowerment

**Definition**
Empowerment is the **primary optimization objective** of the system.

An interaction is empowering if it:
1. respects user autonomy
2. builds or preserves capability
3. aligns with user-stated goals
4. supports long-term wellbeing

**Important**
Empowerment is not a UX feature — it is a **system-level invariant**.

---

## Alienation

**Definition**
Alienation refers to system behaviors that:
- bypass reflection
- erode autonomy
- create dependency
- optimize engagement at the expense of agency

Alienation detection is a **negative constraint** on optimization.

**In Code**

```
modules/empowerment/alienation.py
```

---

## Capability

**Definition**
A capability is a **durable human capacity** (skill, understanding, readiness)
that enables goal achievement.

Products are evaluated by:
- which capabilities they enable
- what prerequisites they require
- what effort they demand

Capabilities persist beyond a single transaction.

---

## Memory (Agentic Memory)

**Definition**
Memory enables continuity, learning, and agency.

| Type | Description |
|----|------------|
| Working memory | In-session state |
| Episodic memory | Reflections on outcomes |
| Semantic memory | Long-term goals, values, capabilities |

Without memory, the system is reactive.
With memory, the system is **agentic**.

---

## Reflection Loop

**Definition**
The reflection loop is a mandatory feedback mechanism where the system asks:

> "Did this action actually help?"

Reflection updates memory and influences future decisions.
It replaces passive behavioral telemetry.

---

## MCP — Model Context Protocol

**Definition**
MCP defines how system capabilities are exposed as **LLM-callable tools**.

It enables:
- Gemini / GPT integration
- tool-based reasoning
- portability across LLM platforms

MCP contains **interfaces only**, never business logic.

---

## Agent (Façade Agent)

**Definition**
An agent is a **thin orchestration wrapper** that:
- coordinates module calls
- manages execution order
- adapts to LLM or UI constraints

Agents do not:
- define objectives
- score outcomes
- override empowerment logic

---

## Objective Function

**Definition**
The objective function defines what the system optimizes for.

In this system:
- not clicks
- not conversion
- not engagement
- **empowerment, agency, alignment**

Changing the objective function changes the entire system.

---

## Summary Statement

> CCO defines *what is optimized*.
> AIS defines *what is allowed*.
> Agentic Commerce defines *where it runs*.
> Memory defines *who the system remembers*.

---

**End of Glossary**
