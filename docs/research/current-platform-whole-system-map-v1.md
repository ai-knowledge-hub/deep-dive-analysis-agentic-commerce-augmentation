# Current Platform Whole-System Map v1

Status: research snapshot; no longer the current implementation authority

Date: 2026-08-25
Last verified: 2026-09-05
Current authority: `docs/platform-modernisation-plan-v2.md`,
`docs/app-architecture.md`, and accepted governance contracts

Scope: repository baseline at 2026-08-25 plus the bounded post-PR #120 delta
below

## Post-PR #120 architecture delta

PR #120 completed the Slice 5 execution boundary that this map described as
planned. The current sequential runtime now canonicalizes executable inputs
before approval; persists exact approval decisions and immutable effect-start
snapshots; consumes authorization atomically with lease, status, and action
budget checks; records durable provider and governed-effect receipts; exposes
tenant-authorized reconciliation for uncertain outcomes; and protects
projection recovery and retry/change-plan identity under concurrent writes.

Migrations 044-049 carry that authority and receipt model across old/new writer
skew. Governed lab promotion additionally revalidates tenant, experiment,
variant, and source-metric relationships at the final commit boundary. The
runtime remains sequential: workflow graph execution, task attempts, parallel
subagents, general evidence/result/completion semantics, and automatic harness
promotion are not implemented by this delta.

The remainder of this document is the ratified 2026-08-25 snapshot. Where it
calls exact approval planned or treats the agentification checkpoint as current,
the delta above and the authoritative documentation index take precedence.

## 1. Executive decision

The platform should be understood as two coupled systems with one governed
control boundary:

1. a **commerce optimisation and learning engine** that discovers intent,
   builds evidence, simulates and compares representations, validates results,
   updates scoped beliefs, and reuses validated learning; and
2. an **agent execution control plane** that turns an objective into bounded
   actions, checks identity, tenancy, policy, effect class, budget, harness,
   registry version, and release posture, executes approved capabilities, and
   records inspectable events and receipts.

The system's whole-purpose output is not an LLM answer or a high lab score. It
is a **traceable improvement decision about a commerce representation**, with
enough evidence and authority to recommend, validate, promote, or reject it,
and with observed outcomes feeding later decisions.

The smallest coherent target architecture preserves the current domain and
runtime assets but evolves the fixed action queue into a durable workflow
kernel. The model remains a non-authoritative reasoner. The host remains the
authority for identity, scope, policy, approval, budgets, execution, state
commit, and completion.

## 2. Evidence boundary and status language

This analysis inspected:

- the repository structure and composition root;
- domain, application, infrastructure, API, web, schema, and migration code;
- the current agent runtime, capability registry, policy, harness, worker,
  external-agent, validation, protocol, belief, memory, and experiment paths;
- canonical modernisation, security, safety, deployment, integration, and
  refactor documents;
- architecture, safety-traceability, and security-traceability executable
  checks.

Status terms used below:

| Status | Meaning |
| --- | --- |
| Implemented | Executable code exists on an active path and has repository evidence. |
| Partial | A useful path exists, but the contract, adapter, deployment, or safety boundary is incomplete. |
| Contracted | A domain/ADR/schema or registry boundary exists but the runtime path is not implemented. |
| Planned | Canonical plan names the work; no complete executable path exists. |
| Inferred | A design conclusion follows from evidence but is not itself a committed product decision. |

The documentation occasionally lags implementation. For example,
`docs/external-integrations.md` still calls agent operator mode planned even
though the runtime and APIs exist. Code, tests, the modernisation plan, and the
agentification checkpoint take precedence over isolated stale wording.

The map was reconciled on 2026-08-25 after the Phase 1 security-authority
hardening. `domain/security/contract_v1.py` is now the immutable schema-v1
authority for all 17 threat closure requirements and mandatory blocked runtime
capability, tool, effect, gate, control, and verification tuples. The runtime
release policy and security catalog are projections of that authority. This
strengthens the current beta boundary but does not implement the exact approval,
durable workflow, parallel-worker, or harness-promotion controls described as
planned below.

Ratification verification on 2026-08-25 collected 441 backend tests and
completed with 440 passed and 1 skipped. Architecture, safety, security, and
repository-quality gates remain the release evidence rather than this document
alone.

## 3. Purpose, actors, and success

| Actor | Desired outcome | Invariant | Observable success | Bears failure |
| --- | --- | --- | --- | --- |
| Commerce operator | Improve product discoverability without manually driving every technical step. | Risky changes remain reviewable and reversible. | A useful recommendation, approved action, and measured outcome are connected by evidence. | Operator and commerce organisation. |
| Brand/client owner | Improve representation while protecting tenant data and brand intent. | Tenant, brand, product, and canonical-intent scope cannot be substituted. | The selected change is scoped, attributable, and consistent with brand constraints. | Brand/client. |
| External agent/integrator | Invoke a stable platform capability without imitating the UI. | Signed identity, least-privilege scopes, idempotency, and receipts. | Retry-safe job creation and a verifiable result or failure. | Integrator and platform operator. |
| Platform operator | Supervise work, policy, recovery, and model/provider posture. | Durable state and audit remain authoritative over UI/model narrative. | Runs can be inspected, paused, retried, reconciled, and explained. | Platform team. |
| End customer | Receive a more discoverable and accurate product representation. | Lab or synthetic evidence is not presented as observed reality. | Real platform outcomes improve without misleading or harmful copy. | Customer and merchant. |

Primary outcome metrics should be real task success, observed discoverability
or representation quality, decision usefulness, safe recovery, and time to an
acceptable outcome. Tool success, model fluency, synthetic win rate, and number
of generated variants are intermediate proxies.

## 4. Whole-system map

```text
USER OR MACHINE PRINCIPAL
  goal / objective / tenant / product / requested capability
                  |
                  v
INTERACTION SURFACES
  Next.js chat + Inbox/Runs/Interventions/Insights + external-agent job API
                  |
                  v
API AND COMPOSITION ROOT
  authentication + tenant resolution + request contracts + dependency wiring
                  |
                  v
AGENT / PLANNING LAYER
  intent inference + explanation + candidate generation + fixed initial plan
                  |
                  v
HARNESS AND CONTROL PLANE
  principal/profile + harness + registry pins + policy + budgets + run state
  + action state + lock/heartbeat + commands + approvals + stopping conditions
                  |
                  v
CAPABILITY EXECUTION
  experiment | validation | protocol readiness/discovery | learning | promotion
                  |
                  v
DOMAIN AND EXTERNAL REALITY
  products + merchant metadata + model providers + search + observed outcomes
                  |
                  v
EVIDENCE AND LEARNING
  snapshots -> metrics -> validation -> belief revision -> calibration -> memory
                  |
                  +-----------> later prompts, queries, variants, decisions

Cross-cutting: tenant scope, provenance, versions, hashes, audit events,
release gates, security controls, safety constraints, and operator recovery.
```

The current system is synchronous and sequential at the action-runtime core.
The planned system introduces a durable workflow, task, attempt, assignment,
join, checkpoint, and projection layer between planning and execution.

## 5. Module map and dependency interactions

### 5.1 Presentation and control-plane module

**Location:** `web/`

**Responsibilities:** present chat, Inbox, Runs, Interventions, Insights/Learnings,
Lab, validation, experiment, evidence, simulation, and admin workflows; collect
operator commands; render state, risk, provenance, and recovery.

**Dependencies:** FastAPI contracts, Clerk session context, tenant context, and
frontend read models.

**Outputs:** objectives, commands, approvals/rejections, observed results,
configuration changes, and user-visible projections.

**Current limitations:** product-discovery chat and run/operator chat are still
separate interaction models; page-owned data fetching and overlapping Lab
surfaces remain; projection lag is not modeled as a first-class state.

### 5.2 API and composition module

**Location:** `api/`, especially `api/main.py` and `api/composition.py`

**Responsibilities:** expose HTTP routes; authenticate human and agent callers;
derive tenant/principal context; validate transport payloads; wire application
ports to concrete repositories, LLM adapters, protocol adapters, and search.

**Dependencies:** application services and infrastructure adapters. This is the
only intended assembly boundary that sees both.

**Outputs:** typed API responses, errors, callback contracts, job receipts, and
application service calls.

**Key invariant:** application code must not import infrastructure. The
architecture check currently passes with no import cycles, although the
composition root is at its configured coupling ceiling.

### 5.3 Conversation and intent module

**Location:** `domain/conversation`, `domain/intent`,
`application/services/conversation`, `application/agents`, and supporting LLM
adapters.

**Responsibilities:** preserve session/turn context; clarify goals; classify
intent; search and compare products; explain recommendations; optionally run
web research and protocol analysis.

**Dependencies:** session repositories, semantic memory, commerce search,
alignment services, LLM gateway, research tools, and replay logging.

**Outputs:** inferred intent, goals, commerce plans, recommendations, research
evidence, explanations, and session state.

**Causal role:** converts ambiguous language into candidate operational scope.
It may propose meaning, but it does not attest tenant ownership, permission, or
execution authority.

### 5.4 Evidence, alignment, and protocol intelligence module

**Location:** `domain/alignment`, `domain/evidence`, `domain/protocol`,
`application/services/evidence`, `infrastructure/alignment`, and
`infrastructure/protocol`.

**Responsibilities:** extract signals, score goal/product alignment, normalize
evidence, inspect ACP/UCP readiness, discover eligible candidates, and produce
structured read-only adapter receipts.

**Dependencies:** catalog/product state, canonical intent specs, live or local
protocol metadata, search/retrieval, and optional LLM reasoning.

**Outputs:** alignment scores, evidence records, readiness summaries,
candidate sets, blockers/warnings, provenance, and receipts.

**Current boundary:** UCP/ACP discovery and readiness are implemented as
read-only intelligence. Checkout, delegated payment, and browser fallback are
non-executable readiness contracts. They are not commerce transaction tools.

### 5.5 Query-battery and audience module

**Location:** `application/services/query_battery`, `domain/intent`, and
catalog/search repositories.

**Responsibilities:** generate top-down, bottom-up, or hybrid query sets;
segment audience intent; enforce leakage, category-confidence, specificity,
and pattern gates; optionally expand candidates with an LLM.

**Dependencies:** canonical intent spec, product/brand context, audience
archetypes, memory artifacts, deterministic generators, and LLM generation.

**Outputs:** persisted query batteries, accepted queries, rejected candidates
with reasons, and generation evaluation events.

### 5.6 Simulation module

**Location:** `domain/simulation` and `application/services/simulation`.

**Responsibilities:** run a sandboxed representation comparison, analyze gaps,
propose revisions, retest, rank candidates, and derive lessons.

**Dependencies:** queries, products/copy, search/retrieval, alignment scoring,
LLM optimization, and replay/session context.

**Outputs:** simulation runs, candidate copy revisions, scores, retest results,
and lessons. These are lab evidence, not production facts.

### 5.7 Experiment module

**Location:** `application/services/experiment` and experiment repositories.

**Responsibilities:** define experiments and variants; freeze retrieval
snapshots; enforce baseline-first comparison; run variants; compute metrics and
statistics; combine experimental, synthetic, and observed signals; recommend
next tests; record promotion decisions.

**Dependencies:** query batteries, retrieval, simulation/copy generation,
validation, belief/calibration data, product catalog, and LLM generation/judging.

**Outputs:** hypotheses, immutable retrieval snapshots, variants, run metrics,
posterior/decision payloads, recommendations, and promotion readiness.

**Validity property:** frozen `snapshot_version` prevents a candidate and its
control from being compared against different retrieval worlds.

**Known gap:** the ML orchestrator does not yet load historical experiments;
its initialization is explicitly a TODO, so claims of trained cross-run ML
optimisation would be inaccurate.

### 5.8 Validation module

**Location:** `application/services/validation_service.py`, validation provider
adapters, API routes, and validation repositories.

**Responsibilities:** create validation jobs; run in-app synthetic judges;
launch provider-native validation; verify callbacks; ingest observed reality;
normalize and persist results.

**Dependencies:** model provider configuration, experiment/copy payloads,
callback tokens, external provider UX, and manual or analytics observations.

**Outputs:** job state, normalized result, winner/score, callback receipt, and
observed-vs-synthetic agreement signals.

**Current modes:** in-app BYOK, ChatGPT MCP provider flow, and manual fallback
are implemented. Gemini function-call execution is contracted but returns 501.

### 5.9 Learning, belief, calibration, and memory module

**Location:** `application/services/loop`, `domain/memory`, loop repositories,
and scheduled maintenance scripts.

**Responsibilities:** version world state; update beliefs from weighted
evidence; record decisions; measure synthetic/observed drift; distill reusable
artifacts; retrieve scoped, quality-gated, fresh memory; periodically
recalibrate.

**Dependencies:** validation results, experiment metrics, tenant/brand/product
scope, provider calibration, and artifact provenance.

**Outputs:** belief revisions, posterior/confidence, decision events,
calibration profiles, memory artifacts, and maintenance history.

**Current learning semantics:** Bayesian-style state adaptation and retrieval,
not foundation-model weight training. Memory promotion uses quality/support
thresholds and contradiction penalties, but the stronger versioned evidence,
rollback, and contradiction lifecycle in the safety plan is not fully built.

### 5.10 Agent runtime and governance module

**Location:** `application/services/agent_runtime`, agent repositories, agent
routes, and runtime scripts.

**Responsibilities:** create principal-aware runs; build an initial action
queue; pin registry/tool/skill versions; apply harness and policy posture;
approve/reject actions; claim and execute actions; enforce budgets; record
events; pause/cancel/retry/recover; expose registry and audit state.

**Dependencies:** all executable domain capabilities, agent run/action/event
stores, principal authentication, harness/registry persistence, and operator or
external-agent commands.

**Outputs:** run/action states, capability effects, output hashes, audit events,
recovery proposals, and user/machine-facing status.

**Current execution semantics:** fixed deterministic initial planner,
single-lane sequential worker, per-run lock and heartbeat, atomic action claim,
bounded worker ticks, and policy checks before execution.

**Planned evolution:** dynamic graph revisions, independently retryable tasks
and attempts, leases/fencing, checkpoints, durable commands, fan-out/join,
isolated workers, and bounded delegation.

### 5.11 External-agent facade

**Location:** external-agent API routes, principal utilities, external-agent job
repositories, and `docs/external-agent-job-contracts.md`.

**Responsibilities:** let another application or agent use the platform as a
module through signed machine identity, scoped tools/skills, idempotent job
creation, linked agent runs, activity projections, and signed receipts.

**Dependencies:** principal tokens, active principal rows, registry discovery,
agent runtime, idempotency reservations, and HMAC signing.

**Outputs:** stable job IDs, retry-safe status, linked events, domain summaries,
and signed evidence digests.

**Current gap:** issuer/admin APIs for credential issuance, rotation, and
revocation are not complete; HMAC is currently issuer-managed with one
configured key family.

### 5.12 Persistence and operational infrastructure

**Location:** `infrastructure/db`, `shared/db`, scripts, and deployment config.

**Responsibilities:** persist tenant catalog, conversation, experiment,
validation, learning, registry, run/action/event, and external-job state;
bootstrap/migrate SQLite; run schedulers and maintenance.

**Dependencies:** filesystem-backed SQLite in the current deployment, process
scheduler, and environment secrets.

**Outputs:** durable rows, migration state, background work, and operational
history.

**Scalability boundary:** SQLite plus an in-process interval scheduler is
suitable only for an explicitly constrained single-node beta. Concurrent
multi-tenant execution requires a production database and durable queue or an
equivalent workflow engine.

## 6. Dependency and authority rules

The architectural dependency direction is:

```text
domain <- application ports/services <- API composition -> infrastructure
                                      <- API routes <- web/external callers
```

The causal and authority direction is different:

```text
principal identity and tenant authority
  -> allowed harness/policy/registry/capabilities
  -> plan proposal
  -> structural and release validation
  -> approval or auto-execution decision
  -> capability effect
  -> authoritative observation/receipt
  -> belief/memory candidate
  -> validated learning
```

No later model-generated narrative may retroactively manufacture authority for
an earlier step. A readable product name, confidence score, LLM-selected tool,
or memory artifact is never sufficient execution identity.

## 7. Current causal flows

### 7.1 Operator-led optimisation success path

1. Operator supplies a tenant-scoped product goal.
2. Conversation/intent services infer goals and build context.
3. Query/simulation/experiment services construct a baseline and candidate.
4. Retrieval is frozen; the control is scored before candidate comparison.
5. Synthetic and/or observed validation produces separately labeled evidence.
6. The deterministic decision policy combines experiment, synthetic, and
   observed signals with reliability and coverage.
7. The runtime proposes the next action under a pinned registry and harness.
8. Policy and operator approval gate consequential effects.
9. The capability executes and records outputs, hashes, events, and anchors.
10. Observed outcomes update calibration, scoped beliefs, and eligible memory.
11. Later query/copy generation retrieves qualified artifacts and therefore
    starts from better evidence.

### 7.2 External-domain embedding path

An external retail assistant, merchant dashboard, content system, CRM, or
market-research application can treat this platform as a bounded optimisation
subsystem:

```text
host-domain object and user objective
  -> host maps object to platform tenant/brand/product/native reference
  -> external-agent token supplies principal and least-privilege scopes
  -> idempotent platform job requests one registry capability or skill
  -> linked run executes or pauses under platform policy
  -> signed receipt + evidence/provenance return to host
  -> host decides how the result affects its own domain lifecycle
```

The embedding contract should preserve the host's native object identity and
domain decision authority. The platform can return a recommendation,
readiness finding, candidate representation, validation result, or approved
effect receipt. It must not pretend that a generic `product_id` captures every
domain's hierarchy, legal state, or publication semantics.

### 7.3 Read-only protocol intelligence path

1. A caller requests ACP/UCP discovery or readiness.
2. Tenant and optional brand/product scope are verified.
3. The read-only adapter uses opted-in, allowlisted live endpoints or local
   metadata fallback.
4. Candidate source and live/fallback provenance are retained.
5. The adapter returns readiness, blockers, warnings, and a receipt.
6. The caller may reason about merchant readiness but gains no checkout or
   payment authority.

### 7.4 Learning loop path

1. Validation or experiment evidence is normalized with source/provider scope.
2. Calibration influences evidence likelihood and confidence.
3. A belief revision appends prior, likelihood, posterior, confidence, and
   evidence reference.
4. Maintenance distills supported revisions into candidate memory.
5. Quality, support, freshness, scope, and contradiction checks filter retrieval.
6. Retrieved memory informs later queries, copy generation, or decisions.

This is a causal learning loop because later system inputs change based on
observed prior outcomes. It is not autonomous model retraining.

## 8. LLM accommodation: what the platform provides

### 8.1 Reasoning freedom

LLMs are currently used for intent classification, goal interpretation,
research synthesis, copy and variant generation, query expansion, product
reasoning, and synthetic judging. The target workflow planner will also allow
models to propose task graphs and revisions.

The platform should expose semantic capabilities with schemas and normalized
failures so stronger models can choose better evidence, ordering, and recovery
paths without changing invariant code. Over-prescribing a fixed sequence would
trap future model intelligence; permitting the model to commit authority or
effects would collapse the safety boundary.

### 8.2 Harness state

Current harness profiles define:

- default and allowed run modes;
- default and allowed policy profiles;
- allowed effect classes;
- planner mode;
- retry and fallback strategies;
- approval strategy;
- memory policy; and
- stopping conditions.

Runs also carry capability allowlists, budgets, registry version/fingerprint,
tool and skill lineage, principal/profile identity, and action/event state.
This is already more than a prompt wrapper: it is a bounded execution posture.

The target harness adds isolated context capsules, token/time/concurrency/depth
budgets, typed worker results, durable attempts, checkpoints, and supplemental
versioned harness candidates.

### 8.3 Security posture

Implemented controls include trusted principal/tenant resolution, host-side
capability and effect checks, action/cost/variant budgets, external-job
idempotency, expiring single-use validation callbacks, signed job receipts,
registry fingerprints, input/output schema checks, run locks, and beta release
gates. The immutable schema-v1 security contract independently pins closure
requirements for every threat and the mandatory blocked production capability
tuples consumed by runtime admission and pre-effect policy.

Material controls still planned include exact-payload approval binding,
authenticated durable workflow commands, leases and fencing tokens, minimal
secret-free context capsules, untrusted-content labeling/scanning, typed child
results, vault-backed secret handles, full egress controls, atomic
multidimensional reservations, cancellation propagation, projection-lag
visibility, dependency bulkheads, and inter-agent message controls.

Therefore the current platform is suitable for bounded supervised and
low-risk sequential work, not unrestricted autonomous parallel execution.

### 8.4 Scalability posture

Current scalability mechanisms are bounded ticks, per-run locks, maximum runs
and steps per cycle, basic budgets, tenant-scoped queries, and provider
selection. They constrain work but do not provide horizontal scheduling,
fairness, backpressure, atomic resource reservation, or dependency isolation.

The target needs:

- PostgreSQL or another concurrency-safe durable store;
- a durable queue/workflow engine;
- tenant and connector concurrency bulkheads;
- atomic reservations for tokens, cost, actions, time, depth, and fan-out;
- rate limiting, circuit breakers, timeout policies, and backpressure;
- attempt leases, fencing, crash recovery, and idempotent effect reconciliation;
- payload/reference storage limits and retention rules; and
- model/provider routing based on capability, latency, cost, and evaluation.

### 8.5 Validity posture

Current validity mechanisms include deterministic keyword fallbacks, structured
schemas, confidence and alignment scoring, source URLs, replay records,
retrieval snapshots, baseline-first gating, separate synthetic and observed
signals, Bayesian-style weighting, calibration drift, quality/support memory
gates, output receipt validation, and human review.

The remaining validity work is system-level: evidence completeness and
freshness contracts, contradiction lifecycle, versioned source authority,
approval bound to exact evidence, evaluation datasets, model/prompt/provider
pins on every consequential inference, deterministic replay boundaries, and
tests for partial-success laundering.

### 8.6 Improvement and self-learning

There are four distinct improvement loops and they must not be conflated:

| Loop | Current status | What changes | Authority requirement |
| --- | --- | --- | --- |
| In-run reasoning | Implemented/partial | Model proposes better interpretation, copy, queries, or evidence use. | Host validates schemas, scope, policy, and effects. |
| Domain learning | Implemented/partial | Beliefs, calibration, decisions, and retrieved memory change from evidence. | Evidence provenance, tenant scope, support, quality, and contradiction checks. |
| Model selection/prompt evaluation | Partial | Provider/model/prompt choice may improve quality, cost, or latency. | Version pins, offline/online evals, staged rollout, rollback. |
| Harness self-refinement | Contracted/planned | Supplemental prompts, skills, memories, or worker specs become candidates. | Immutable base, scoped candidate, representative eval, human/policy approval, activation receipt, rollback. |

The correct long-term pattern is **candidate improvement, not silent
self-modification**:

```text
trajectory or outcome evidence
  -> candidate belief/memory/harness change
  -> provenance and contradiction checks
  -> offline evaluation and adversarial tests
  -> bounded shadow/canary deployment
  -> policy or human approval
  -> immutable activation version
  -> runtime monitoring
  -> retain, narrow, or roll back
```

Improving model intelligence should reduce clarification, tool calls, latency,
and rigid navigation. It must not remove tenant isolation, evidence provenance,
approval for irreversible effects, or host-owned completion.

## 9. Responsibility allocation

| Responsibility | Model | Deterministic host | External authority | Policy/human |
| --- | --- | --- | --- | --- |
| Interpret an ambiguous objective | Proposes hypotheses and uncertainty. | Preserves alternatives and typed intent. | May resolve native objects. | Human clarifies material ambiguity. |
| Select a capability or plan | Proposes capability/task graph. | Validates registry, schema, dependency, budgets, and release status. | None. | Policy constrains; human approves material change. |
| Resolve tenant/product identity | May suggest candidates. | Binds immutable IDs and scope. | Catalog/provider attests current object. | Human chooses only when authoritative ambiguity remains. |
| Determine permission | No authority. | Authenticates claims and computes envelope. | Identity/provider systems attest facts. | Policy authorizes; human approves required effects. |
| Generate copy/query/summary | Generates candidates. | Applies structural, leakage, and output checks. | Source documents remain authoritative. | Human reviews high-impact content. |
| Score experimental evidence | May generate/judge one signal. | Freezes snapshots and computes reproducible metrics. | Observed platforms provide reality signal. | Decision policy weights; human interprets commercial value. |
| Update belief or memory | Proposes interpretation/candidate. | Commits versioned scoped update after gates. | Evidence sources attest observations. | Promotion policy/human governs reusable state. |
| Execute an effect | No direct authority. | Invokes only a bounded adapter and records receipt. | External system commits/reports effect. | Policy and exact approval authorize. |
| Declare completion | May recommend. | Verifies terminal state, mandatory outcomes, receipts, and reconciliation. | External observation may be required. | Human resolves value/outcome exceptions. |

## 10. Environment and integration model

### Local development

Next.js and FastAPI run as separate processes against a local SQLite database.
Developers choose a BYOK provider and can use mocked/local protocol metadata.
This environment optimizes iteration, not concurrency or durable recovery.

### Preview/dev

The documented profile uses hosted frontend/backend processes, provider keys,
optional telemetry, and SQLite. It is appropriate for demonstrations and
controlled testing only if single-node and low-concurrency constraints are
explicit.

### Production as currently documented

The documented production shape is Next.js on Vercel plus FastAPI on a Python
host with filesystem SQLite and an external model provider. This is not a
sufficient final topology for horizontally scaled multi-tenant agent work.
Local database ownership, scheduler duplication, and failover semantics must be
resolved before scaling replicas.

### Embedded platform module

For integration into another domain application, use the external-agent job
and registry contracts as the northbound boundary. Add domain adapters that map
host-native objects to platform references and map platform findings/receipts
back to host decisions. Do not let an embedding application call internal
repositories or capability executors directly; that would bypass tenancy,
idempotency, policy, release gates, and audit.

Recommended integration modes:

| Mode | Example | Allowed output | Required guard |
| --- | --- | --- | --- |
| Advisory | Market-research app asks for protocol readiness. | Finding, evidence, recommendation. | Read-only scopes and freshness/provenance. |
| Content optimisation | PIM/CMS asks for candidate product copy. | Draft or validated candidate. | Native product binding, brand constraints, no implicit publish. |
| Supervised action | Merchant console asks to promote a lab winner. | Approved internal state effect and receipt. | Exact approval, idempotency, rollback owner. |
| Observational feedback | Analytics/CRM returns real outcome. | Normalized observation and calibration input. | Source identity, event dedupe, completeness, tenant scope. |
| Future transactional | Commerce host asks for checkout/payment effect. | External operation receipt. | Separate product decision; transaction-grade authority, reconciliation, and compliance. Currently excluded. |

## 11. State and lifecycle

### Current durable state families

- conversation: sessions, turns, goals, episodes, recommendations, replays;
- catalog: clients, brands, products, platform profiles, canonical intent specs;
- experiment: batteries, queries, experiments, hypotheses, variants, snapshots,
  runs, metrics, recommendations;
- validation: jobs, results, callbacks, observed validations, calibration;
- learning: world states, belief revisions, decision events, memory artifacts;
- runtime: principals, profiles, harnesses, policies, registry versions, runs,
  actions, events, external jobs, receipts.

These states should remain separate. Conversation history is not execution
state; execution checkpoints are not beliefs; beliefs are not permissions;
memory is not source authority; a UI projection is not lifecycle truth.

### Current runtime lifecycle

Runs are planned, running, paused, completed, failed, or canceled. Actions are
proposed, approved, executing, executed, failed, or rejected. Retry creates a
new action rather than rewriting a failed action. Per-run locks and atomic
claims reduce duplicate sequential execution.

### Target lifecycle

The accepted ADR separates workflow, immutable graph revision, task, attempt,
agent assignment, action, approval, result, receipt, checkpoint, and event.
This separation is required before parallelism because each concept has
different retry, authority, and terminal semantics.

## 12. Representative failure scenarios

### Ambiguous product reference

The model may return candidates. A catalog/provider resolver must attest native
identity and tenant scope. One complete match may proceed; multiple material
matches require clarification. The selected name is rebound to a current ID
before execution.

### Unauthorized cross-tenant job

The bearer token, not request parameters, supplies external principal and
tenant. Requested tool/skill scopes are intersected with registry and harness
limits. The request is rejected before planning and no partial run should be
created outside the authenticated scope.

### Partial or stale validation

Synthetic evidence remains labeled synthetic; incomplete observed coverage
cannot be summarized as production readiness. The decision output must retain
coverage, reliability, source, version, and missing evidence. Promotion stays
at lab or is blocked.

### Crash after an external effect

Current read-only and internal beta boundaries reduce exposure, but the future
external-write path must reconcile using an idempotency key and provider
operation ID before retry. A missing local receipt means uncertain outcome,
not permission to repeat the effect.

### Concurrent workers

Not supported by the current execution model. The target reserves budgets
atomically, issues assignment-scoped authority, isolates contexts/workspaces,
uses attempt leases and fencing, validates typed results, and lets only the
coordinator commit shared state.

### Poisoned retrieved content

Content is labeled as untrusted evidence and may inform model reasoning. It
cannot alter policy, capability scopes, approval, harness configuration, or
completion. Current prompt/data separation is not yet fully enforced across
all future worker paths, so parallel or recursive execution remains excluded.

### Better model version

A new model may generate a different plan or require fewer calls. Run it
against outcome, safety, recovery, and cost evaluations while registry,
authority, and policy invariants remain fixed. Promote through a versioned
rollout; do not loosen invariants merely because average model performance rose.

## 13. Whole-system risks

| Risk | Current condition | Impact | Required response |
| --- | --- | --- | --- |
| Static planner ceiling | Fixed queue from allowed capabilities. | Better models cannot dynamically decompose or recover. | Versioned planner contract and immutable graph revisions. |
| SQLite/scheduler ceiling | Filesystem DB and per-process loop. | Split brain, contention, duplicated schedules, weak failover. | Constrained beta or durable DB/queue before scale. |
| Approval under-binding | Current approvals do not yet bind every future payload/evidence/authority/revision dimension. | Substitution or stale approval. | Exact approval object with expiry/revocation and hash checks. |
| Learning authority leakage | Memory/belief artifacts may be treated as facts beyond their evidence. | Persistent wrong decisions or cross-scope contamination. | Versioned evidence ledger, contradiction/retirement, rollback, coordinator-only commit. |
| Synthetic metric substitution | Lab/synthetic wins become perceived production truth. | Commercially wrong deployment. | Separate signal labels, observed thresholds, outcome evaluation. |
| Partial-success laundering | Summary omits failed actions, missing pages, or stale evidence. | False completion and operator trust loss. | Typed completeness, projection lag, mandatory missing/partial fields. |
| Retry amplification | Scheduler, command retry, provider retry, and capability retry compose. | Cost and duplicate effects. | One retry owner per layer, aggregate budgets, durable attempts, effect reconciliation. |
| Context/secret leakage | Provider prompts, logs, tool output, and future child context share data. | Tenant or credential disclosure. | Minimal capsules, opaque secret handles, redaction, egress and telemetry policy. |
| Registry/config drift | Static and persisted harness/registry sources coexist. | Historical run semantics become unclear. | Immutable releases, producer/consumer pins, migration and rollback rules. |
| Safe deadlock | Observe/human-required posture can block the discovery needed to make work safe. | Unusable automation and excessive clarification. | Permit bounded authoritative reads; return normalized blockers and recovery options. |

## 14. Recommended implementation order

1. **Complete exact approval authority.** Define one immutable authorization
   envelope and independent lifecycle, persist it, and revalidate every bound
   identity, payload, evidence, authority, revision, policy, and version
   immediately before a governed effect.
2. **Define evidence, result, and completion contracts.** Preserve freshness,
   provenance, completeness, missing coverage, partial failure, receipt state,
   and projection lag from capability output to operator-visible completion.
3. **Run the sequential workflow compatibility and framework spike.** Represent
   one current ordered agent run as an immutable workflow revision and tasks,
   dual-project existing APIs, and compare internal, LangGraph-style, and
   Temporal-style execution against the accepted recovery and portability
   criteria.
4. **Deliver the chat-first sequential vertical slice.** One conversation and
   command gateway should create, explain, approve, pause, retry, and complete
   an existing safe run with durable receipts.
5. **Build the durable workflow kernel.** Add workflow revisions, tasks,
   attempts, events, checkpoints, idempotent commands, leases, fencing,
   recovery, and compatibility projections.
6. **Replace the deployment bottleneck.** Decide and implement the production
   database and durable queue topology before multi-replica or parallel work.
7. **Strengthen evidence and learning governance.** Version evidence and priors,
   model contradiction/retirement/rollback, bind promotion to exact evidence,
   and prevent memory from becoming authority.
8. **Add bounded parallel read/recommend workers.** Use isolated minimal
   contexts, non-expanding authority/budgets, typed results, deterministic
   joins, and coordinator-only commits.
9. **Add evaluation-driven model and harness evolution.** Begin with provider,
   prompt, and skill candidates; keep base harness immutable; require offline
   eval, shadow/canary evidence, approval, activation receipt, monitoring, and
   rollback.
10. **Consider external writes only as separate releases.** Each adapter needs
   transaction-grade idempotency, provider identity, exact approval,
   reconciliation, compensation, and compliance review.

## 15. Acceptance criteria

The architecture is ready for the next autonomy tier only when:

- every transition is accepted or rejected by one executable lifecycle contract;
- every consequential effect names principal, tenant, native target, tool,
  skill, registry, harness, policy, input hash, approval, and receipt;
- duplicate delivery and crash recovery cannot duplicate a committed effect;
- cancellation, expiry, revocation, and timeout propagate to workers and
  external operations with acknowledged state;
- partial, stale, contradictory, unsupported, and unavailable evidence remain
  visible through summaries and decisions;
- belief and memory updates retain prior/evidence versions, provenance,
  calibration, contradiction state, and rollback path;
- a child or embedded caller cannot expand tenant, capability, effect, or any
  budget dimension;
- parallel results cannot mutate shared state before coordinator validation;
- system evaluation measures outcome, false acceptance, false rejection,
  recovery, latency, cost, and operator comprehension;
- changing the model or prompt cannot bypass unchanged authority and safety
  tests;
- production topology passes concurrency, restart, queue, database, provider
  degradation, and noisy-neighbour tests; and
- UI projections declare freshness and cannot report complete before durable
  outcome and receipt gates pass.

## 16. Open decisions and falsifiable assumptions

| Decision or assumption | Current evidence | Risk if wrong | Evidence/decision needed |
| --- | --- | --- | --- |
| The primary product outcome is commerce representation optimisation, not transaction execution. | README, modernisation beta scope, release gates, readiness-only protocol contracts. | Architecture could optimize the wrong domain boundary. | Product decision before any checkout/payment work. |
| SQLite can support the intended beta load. | Current deployment and sequential locks. | Contention, split brain, lost availability. | Explicit concurrency/SLA limits and load/failover test, or move to durable shared storage. |
| Observed validation is available with sufficient quality and coverage. | Manual/external ingestion exists; GA4 native connector is absent. | Learning optimizes synthetic proxies. | Define source integrations, completeness, identity, and minimum evidence SLAs. |
| Bayesian-style update is appropriate for all belief types. | Current scalar prior/likelihood implementation. | Miscalibrated or semantically invalid confidence. | Domain-specific calibration study and posterior predictive checks. |
| Memory quality/support thresholds generalize across tenants and artifact types. | Global constants and contradiction penalty. | Useful learning suppressed or poor learning promoted. | Per-artifact evaluation and tenant-aware calibration policy. |
| External consumers can map stable native identities. | External job API exists; generic product scope dominates internal workflows. | Semantic compression and wrong-domain effects. | Integration-specific identity/provenance contracts and golden fixtures. |
| A workflow engine should be internal, graph-based, or Temporal-like. | ADR deliberately defers technology choice. | Premature lock-in or missing recovery semantics. | Vertical spike comparing required leases, events, joins, replay, operations, and migration cost. |
| Harness refinement can safely improve performance. | Research and safety contracts only; automatic promotion excluded. | Persistent behavior drift or feedback poisoning. | Representative eval set, promotion policy, canary, regression attribution, and exact rollback proof. |

## 17. Traceability anchors

- Product purpose and current capability: `README.md`
- Current module map: `docs/app-architecture.md`
- Canonical target and delivery sequence: `docs/platform-modernisation-plan-v2.md`
- Current execution plan: `docs/platform-modernisation-plan-v2.md`
- Agent runtime direction: `docs/agentic-layer.md`
- Learning loop: `docs/architecture-learning-loop.md`
- External integrations and deployment: `docs/external-integrations.md`,
  `docs/deployment.md`
- External embedding contract: `docs/external-agent-job-contracts.md`
- Workflow schema: `docs/decisions/0001-workflow-task-delegation-schema.md`
- Workflow lifecycle: `domain/workflow/lifecycle.py`
- Security model: `docs/security/agent-workflow-threat-model-v1.md` and
  `docs/security/security-controls-v1.yaml`
- Immutable schema-v1 security authority: `domain/security/contract_v1.py`
- Safety model: `docs/safety/stpa-workflow-control-analysis-v1.md` and
  `docs/safety/safety-controls-v1.yaml`
- Runtime execution: `application/services/agent_runtime/runtime/service.py`
- Capability execution: `application/services/agent_runtime/capabilities/executor.py`
- Harness posture: `application/services/agent_runtime/registry/harnesses.py`
- Learning implementation: `application/services/loop/`
- Dependency wiring: `api/composition.py`

## 18. Bottom line

The existing build is not a loose collection of LLM features. It already has
the beginnings of a governed agent platform: clean application boundaries,
typed capabilities, principal-aware runs, harness and policy posture, bounded
execution, evidence separation, audit events, signed external-job receipts,
and an adaptive belief/memory loop.

Its current safe operating envelope is narrower than its target narrative:
sequential supervised or low-risk work, read-only external protocol
intelligence, synthetic plus manually observed validation, and scoped adaptive
memory. Dynamic workflows, reliable parallel agents, automatic harness
refinement, transaction-grade external effects, and horizontally scalable
operations remain planned.

The architectural strategy should therefore be **preserve the deterministic
authority and evidence spine while increasing model freedom above it**. This
lets better LLMs navigate more of the process, reduce operator friction, and
discover better plans without allowing fluency, confidence, memory, or
self-generated configuration to become permission or truth.
