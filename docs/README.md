# Documentation Index

Status: current
Last verified: 2026-09-05
Owner: platform architecture
Baseline: `origin/main@96a1c23` (includes PR #120)

This is the authoritative documentation inventory. Every file under `docs/`
must appear exactly once below. A category defines how a document may be used;
status does not turn a reference or research snapshot into current authority.

## Category semantics

- `canonical-plan`: current delivery sequence and product/architecture scope.
- `durable-decision`: accepted decisions authoritative until superseded.
- `executable-governance`: normative safety, security, or quality material enforced by CI.
- `current-implementation`: verified description of code that exists now.
- `current-product-guide`: current operator, UX, or product behavior.
- `reference-design`: useful guidance that is not current implementation authority.
- `research-snapshot`: dated evidence; revalidate before using as current fact.
- `operational-record`: deployment, incident, or risk information.
- `historical`: retained context that must not direct current work.

Authority namespaces are closed by default: files under `docs/decisions/`
must be durable decisions, files under `docs/safety/` and `docs/security/`
must remain executable governance, and files under `docs/history/` must remain
historical. The first agentification checkpoint and completed cleanup plan are
also pinned as historical; moving them back into current authority requires an
explicit contract change, not an inventory edit.

## Authoritative inventory

The verification and baseline columns are mandatory for every non-historical
entry. The inventory row is the canonical metadata record; a document may
repeat that metadata in its own header for readability. `make docs-check`
validates this inventory and repository-local links.

| Path | Category / authority | Status | Purpose | Owner | Last verified | Baseline / supersession |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/README.md` | executable-governance | current | Authoritative documentation inventory and category policy. | platform architecture | 2026-09-05 | `origin/main@96a1c23` |
| `docs/agent-capability-map.md` | reference-design | reference | Map product verbs to agent skills, tools, and intended capabilities. | product and agent runtime | 2026-09-05 | Recheck implementation statuses before use. |
| `docs/agent-first-modular-architecture-v1.md` | reference-design | reference | Describe the target modular agent-first architecture. | platform architecture | 2026-09-05 | Subordinate to Plan v2 and accepted ADRs. |
| `docs/agentic-layer.md` | current-implementation | current | Describe the implemented agent-runtime layer and remaining roadmap. | agent runtime | 2026-09-05 | `origin/main@96a1c23` |
| `docs/agentification-checkpoint.md` | historical | historical | Preserve the first agentification implementation checkpoint. | platform architecture | 2026-06-17 | Superseded by `docs/platform-modernisation-plan-v2.md`. |
| `docs/app-architecture.md` | current-implementation | current | Describe current application modules, data, and runtime boundaries. | platform architecture | 2026-09-05 | `origin/main@96a1c23` |
| `docs/architecture-learning-loop.md` | reference-design | reference | Explain the intended evidence, belief, memory, and calibration loop. | learning loop | 2026-09-05 | Validate against current services before implementation. |
| `docs/chat-led-operator-console-spec.md` | reference-design | future-spec | Define the future chat-led operator-console interaction model. | product and design | 2026-09-05 | Current behavior lives in `docs/operator-experience.md`. |
| `docs/codebase-cleanup-and-modularisation-plan.md` | historical | historical | Preserve the completed cleanup and modularisation sequence. | platform architecture | 2026-05-06 | Superseded by `docs/platform-modernisation-plan-v2.md`. |
| `docs/debug/incidents-fixed.md` | operational-record | maintained | Retain resolved incidents and reusable failure lessons. | engineering operations | 2026-09-05 | Append-only operational context. |
| `docs/debug/open-risks.md` | operational-record | maintained | Track unresolved runtime and release risks. | engineering operations | 2026-09-05 | Review before release decisions. |
| `docs/decisions/0001-workflow-task-delegation-schema.md` | durable-decision | accepted | Define workflow, revision, task, attempt, delegation, result, and checkpoint semantics. | platform architecture and agent runtime | 2026-09-05 | Accepted Phase 1 contract. |
| `docs/decisions/README.md` | durable-decision | current | Index accepted architecture decisions. | platform architecture | 2026-09-05 | ADRs are authoritative until superseded. |
| `docs/deployment.md` | operational-record | current | Explain supported environments, migrations, rollout, and runtime operations. | engineering operations | 2026-09-05 | `origin/main@96a1c23` |
| `docs/external-agent-job-contracts.md` | reference-design | current-contract | Describe the current machine-facing external-agent job API. | agent runtime and API | 2026-09-05 | Verify endpoint details against routes and tests. |
| `docs/external-integrations.md` | reference-design | reference | Inventory provider and protocol integrations. | integrations | 2026-09-05 | Some future sections remain explicitly planned. |
| `docs/history/README.md` | historical | historical | Index retained historical documents. | platform architecture | 2026-09-05 | Current authority begins at `docs/README.md`. |
| `docs/history/agent-first-migration-slice-rfc.md` | historical | historical | Preserve rationale for the first agent-first migration slice. | agent runtime | 2026-05-06 | Implemented and superseded by current runtime docs. |
| `docs/history/app-workflows.md` | historical | historical | Preserve the former lab-first workflow map. | product | 2026-05-06 | Superseded by `docs/operator-experience.md`. |
| `docs/history/experiment-flow-detailed.md` | historical | historical | Preserve detailed legacy experiment-flow behavior. | experiments | 2026-05-06 | Reference only. |
| `docs/history/pitch-deck.html` | historical | historical | Preserve the historical product presentation. | product | 2026-05-06 | Not engineering authority. |
| `docs/history/user-guide-complete.md` | historical | historical | Preserve the former human-led user guide. | product | 2026-05-06 | Superseded by `docs/operator-experience.md`. |
| `docs/operator-experience.md` | current-product-guide | current | Describe current operator behavior and intervention surfaces. | product and design | 2026-09-05 | `origin/main@96a1c23` |
| `docs/platform-modernisation-plan-v2.md` | canonical-plan | canonical | Define scope, beta boundaries, architecture direction, and delivery order. | platform architecture | 2026-09-05 | Sole forward execution plan. |
| `docs/research/agent-harness-orchestration-notes-v1.md` | research-snapshot | snapshot | Record research on recursive, parallel, long-running, and continual harnesses. | platform architecture | 2026-08-10 | Revalidate external claims before decisions. |
| `docs/research/current-platform-whole-system-map-v1.md` | research-snapshot | snapshot | Preserve the pre-PR #120 whole-system map and post-#120 delta. | platform architecture | 2026-09-05 | Snapshot at 2026-08-25 plus delta at `origin/main@96a1c23`. |
| `docs/safety/README.md` | executable-governance | current | Index the STPA analysis and executable safety catalog. | safety and platform architecture | 2026-09-05 | Enforced by `make safety-traceability-check`. |
| `docs/safety/safety-controls-v1.yaml` | executable-governance | normative | Define machine-checked safety traceability. | safety and platform architecture | 2026-09-05 | Schema v1, enforced by CI. |
| `docs/safety/stpa-workflow-control-analysis-v1.md` | executable-governance | accepted | Explain the STPA control structure, hazards, scenarios, and constraints. | safety and platform architecture | 2026-09-05 | Phase 1 safety baseline. |
| `docs/security/README.md` | executable-governance | current | Index the threat model, immutable authority, and security catalog. | security and platform architecture | 2026-09-05 | Enforced by `make security-traceability-check`. |
| `docs/security/agent-workflow-threat-model-v1.md` | executable-governance | accepted | Explain threats, boundaries, controls, release decisions, and response. | security and platform architecture | 2026-09-05 | Phase 1 security baseline. |
| `docs/security/security-controls-v1.yaml` | executable-governance | normative | Define machine-checked security traceability and owned gaps. | security and platform architecture | 2026-09-05 | Schema v1, enforced by CI. |
| `docs/terminology.md` | current-implementation | current | Define canonical platform and runtime vocabulary. | platform architecture | 2026-09-05 | `origin/main@96a1c23` |
| `docs/ui-control-plane-simplification-plan.md` | reference-design | remaining-roadmap | Retain completed UI context and the remaining roadmap. | product and design | 2026-09-05 | Current behavior lives in `docs/operator-experience.md`. |
| `docs/ui-style-direction.md` | reference-design | current-rules | Define visual rules for the control-plane UI. | product and design | 2026-09-05 | Apply with the usability gate. |
| `docs/usability-simplification-gate.md` | executable-governance | current | Define UX review rules that hide runtime complexity by default. | product and design | 2026-09-05 | Used by `make web-ui-language-check`. |
| `docs/user-testing-plan.md` | reference-design | evaluation-plan | Define usability evaluation for the operator loop. | product and design | 2026-09-05 | Execute when evaluating UI changes. |
| `docs/ux-flow-schema.md` | reference-design | current-contract | Define cross-surface UX modes and operator/agent transitions. | product and design | 2026-09-05 | Product-level interaction contract. |

## Reading order

For forward work, start with the canonical plan, then the relevant ADR and
executable safety/security governance. Current implementation docs locate code.
Reference designs and research cannot override those authorities. Historical
documents preserve rationale only.

Repository links must be relative so they work in GitHub and every checkout.
Code-spanned paths are also checked for existence. When an incident or migration
record must name a path that no longer exists, prefix it explicitly with
`historical-path:` (for example,
`historical-path:infrastructure/db/old_adapter.py`).
Use `runtime-path:` for an operational location created outside the repository
(for example, `runtime-path:./tmp/local.db`). Unprefixed `./` and `../` values
are always treated as document-relative repository paths, including
extensionless files and directories.

The UX documents have deliberately separate responsibilities:

- `operator-experience.md`: current operator behavior;
- `usability-simplification-gate.md`: review and acceptance rules;
- `chat-led-operator-console-spec.md`: future chat-led interaction reference;
- `ui-control-plane-simplification-plan.md`: remaining UI roadmap only;
- `ux-flow-schema.md`: cross-surface interaction contract;
- `user-testing-plan.md`: evaluation method; and
- `ui-style-direction.md`: visual rules.
