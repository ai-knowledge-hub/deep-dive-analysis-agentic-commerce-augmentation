# Agent Capability Map

Status: current
Last updated: 2026-05-06

This document maps the platform narrative verbs to the agents, skills, tools, and current implementation status that support them. Use it when planning functionality, UX, and agent-runtime work so product language stays connected to executable platform capabilities.

## Narrative Capability Map

| Narrative verb | Agent or skill doing it | Main tools and capabilities | Status |
| --- | --- | --- | --- |
| Product copy needs testing | `Optimize Product Representation` skill | `retrieval.freeze_protocol`, `experiment.run_control_baseline`, `hypothesis.seed`, `variant.generate`, `experiment.run_variant`, `learning.update_posterior_and_decisions`, `policy.recommend_next_action` | Mostly implemented in runtime |
| Evidence needs checking | Evidence/protocol layer plus `Discover Protocol Candidates` skill | `validation.review_readiness`, `learning.update_posterior_and_decisions`, protocol/evidence services, ACP/UCP readiness checks | Partly implemented; protocol execution still maturing |
| Simulations drift | Experiment/runtime agent loop | `retrieval.freeze_protocol`, `experiment.run_control_baseline`, `experiment.run_variant` | Implemented mitigation: frozen retrieval snapshots |
| Validation jobs fail | `Request Validation And Ingest Result` skill plus `Triage Failed Run` skill | `validation.request_synthetic`, `validation.review_readiness`, `run.read`, `event.read`, `policy.inspect`, `run.retry_safe` | Validation implemented; recovery flow partly implemented |
| Policy risks appear | Runtime policy plus operator preflight system | `policy.recommend_next_action`, command preflight, approval/reject commands, Interventions UI | Implemented core guardrails |
| External agents may call the platform | External-agent principal plus job/run API | `POST /external-agent/jobs`, `GET /external-agent/jobs/{job_id}`, `GET /external-agent/jobs/{job_id}/receipt`, `GET /external-agent/jobs/{job_id}/receipts`, `GET /external-agent/jobs/{job_id}/activity`, `GET /external-agent/jobs/{job_id}/events`, `GET /agent-runs/registry`, scoped principal resolution, registry-pinned skills/tools | Idempotent job facade, signed receipt history, scoped event feed, normalized activity projection, and protocol discovery/readiness domain summaries implemented |

## Application Agents

These are the named application-level agents or agent services currently present around the runtime.

| Agent or service | Role |
| --- | --- |
| `CommerceAgent` | Builds commerce plans from operator/user intent. |
| `IntentAgent` | Detects user intent. |
| `ExplainAgent` | Explains recommendations and results. |
| `CapabilityAgent` | Describes available platform capabilities. |
| `BeliefUpdateAgent` | Updates learning and belief state after evidence. |
| `Layer1Agent` | Runs evidence/protocol readiness analysis. |
| `Layer2Agent` | Discovers protocol candidates; currently still mock/placeholder-heavy. |
| `OrchestratorAgent` | Coordinates Layer 1 and Layer 2 agent flows. |
| `AgentRuntimeWorkerService` | Executes runnable agent actions safely under policy. |
| `AgentRuntimePolicy` | Blocks or allows actions based on run mode, capability, tool effect class, and required inputs. |

## Current Executable Runtime Tools

These are the most important executable tools in the current runtime registry.

| Tool | Purpose |
| --- | --- |
| `retrieval.freeze_protocol` | Freeze retrieval snapshots so variant comparisons are fair and time-drift resistant. |
| `experiment.run_control_baseline` | Run the control variant against frozen retrieval snapshots. |
| `hypothesis.seed` | Create hypotheses from baseline gaps and winner-signal deltas. |
| `variant.generate` | Generate candidate product representation/copy variants from evidence and hypotheses. |
| `experiment.run_variant` | Execute a candidate variant against the frozen snapshot set. |
| `validation.request_synthetic` | Request synthetic validation for the selected experiment or variant. |
| `validation.review_readiness` | Review validation and promotion readiness gates without mutating state. |
| `learning.update_posterior_and_decisions` | Refresh posterior and decision outputs from latest evidence. |
| `policy.recommend_next_action` | Recommend the safest next action under current constraints. |
| `promotion.promote_lab` | Promote a variant into the lab progression path. |
| `promotion.promote_prod` | Promote a variant toward production when readiness gates pass. |
| `copy.publish_revision` | Publish an approved copy revision to the product description. |

## Declared Future-Oriented Skills And Gaps

Some skills and tool families are already represented in the platform language but are not fully production-real yet.

| Area | Current meaning | Next build need |
| --- | --- | --- |
| `run-safe-browser-fallback-check` | Declared non-executable readiness boundary for governed browser fallback verification. | Keep market-research-only until narrow browser adapters, permission scopes, receipts, and policy review gates are approved. |
| ACP/UCP execution tools | Protocol discovery/readiness exists; `check_protocol_readiness` and `discover_protocol_candidates` run through registry-declared read-only protocol adapters with structured receipts and activity summaries. Checkout, delegated-payment, and browser fallback remain non-executable readiness boundaries. | Expand read-only retrieval surfaces where merchant endpoints are available; require separate policy review before any side-effecting execution adapter. |
| External-agent job contracts | Idempotent job create/status facade exists, links jobs to agent runs, signs latest-status receipts, stores receipt history, exposes scoped linked-run events, projects normalized activity, and summarizes protocol discovery/readiness evidence. | Add richer scoped credentials, additional domain summaries beyond protocol intelligence, and retry-safe contracts for more endpoints. |
| Harness profiles | `harness_id` is stored on runs. | Make harnesses behavior-defining for planner mode, retries, fallback order, approval strategy, memory policy, and stopping conditions. |

## How To Use This Map

Use this document as a shared product/engineering checklist:

- UX work should make these verbs visible and understandable to operators.
- Runtime work should connect every verb to a skill, tool, policy profile, receipt, and recovery path.
- External-agent work should expose these capabilities through idempotent, scoped, machine-friendly contracts.
- Documentation should prefer these capability names over older lab-first navigation language.
