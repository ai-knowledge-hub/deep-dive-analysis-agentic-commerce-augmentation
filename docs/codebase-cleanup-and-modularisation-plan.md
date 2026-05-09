# Codebase Cleanup And Modularisation Plan

Status: current
Last updated: 2026-05-06

This is the working plan for reducing source entanglement and making the agent-first platform easier for humans and coding agents to change safely. The goal is not a decorative refactor. The goal is less context drag, clearer ownership, smaller active files, and fewer stale paths for future work to trip over.

## Principles

- Inventory before deletion: old does not mean stale if imports or docs still depend on it.
- Delete obvious noise first: generated files, duplicate entrypoints, stale wrappers, obsolete docs.
- Modularise active hotspots next: the files we touch most should be the easiest to reason about.
- Preserve compatibility deliberately: wrappers are acceptable temporarily if Makefile, README, CI, or operators may still call them.
- Keep every cleanup PR verifiable: lint, architecture checks, focused tests, and build should stay green.

## Source Classification

Use these labels when auditing files and folders:

| Status | Meaning | Action |
| --- | --- | --- |
| `active` | Used by runtime, tests, or current docs | Keep and modularise only when it reduces friction |
| `canonical` | Preferred import or execution path | Update Makefile/docs to point here |
| `compatibility-wrapper` | Backwards-compatible shim around canonical code | Keep temporarily, then remove after references are migrated |
| `candidate-stale` | Not imported and not referenced by current docs | Review in a small PR before deleting |
| `historical` | Useful rationale but not active guidance | Move under historical docs or mark clearly |
| `delete-now` | Generated/cache/duplicate with no reason to keep | Remove immediately |

## Current Findings

| Area | Classification | Notes | PR Action |
| --- | --- | --- | --- |
| `domain/` | `active` | Still imported by API, application services, infrastructure adapters, shared transformers, and tests. It is old but not stale. | Do not delete. Keep as pure logic and protect boundaries. |
| `scripts/checks/*` | `canonical` | Real implementations for architecture and bloat checks. | Make Makefile call these directly. |
| `scripts/seed/*` | `canonical` | Real seed implementations. | Make Makefile/docs call these directly. |
| `scripts/ops/*` | `canonical` | Real runtime worker/scheduler/maintenance implementations. | Make Makefile/docs call these directly. |
| root `scripts/*.py` wrappers | `delete-now` | Thin wrappers around canonical modules with references migrated. | Removed in PR2 after Makefile/docs/CI were canonicalized; `make script-entrypoint-check` blocks reintroduction. |
| `docs/agentification-checkpoint.md` | `current` | Active execution checkpoint. | Keep concise; split history out if it grows. |
| `docs/agent-first-modular-architecture-v1.md` | `current` | Active target architecture. | Keep. |
| `docs/operator-experience.md` | `current` | Current operator/user guide for the agentic control plane. | Keep as the canonical UX guide and update after each major UI slice. |
| `docs/chat-led-operator-console-spec.md` | `current/reference` | Still relevant to control-plane UX. | Keep as design reference; trim only after UI settles. |
| `docs/history/user-guide-complete.md` | `historical` | Written for older human-led UX. | Retained as history; superseded by `docs/operator-experience.md`. |
| `docs/history/experiment-flow-detailed.md` | `historical` | Lab-era flow detail. | Retained as history after PR3. |
| `docs/history/app-workflows.md` | `historical/reference` | Contains useful workflow notes but overlaps newer checkpoint docs. | Retained under history after PR3. |
| largest frontend pages | `active-hotspot` | `experiments`, `agent-runs`, `admin`, `validation` are still the largest files. | Modularise only where active development friction is real. |
| `api/routes/agent_runs.py` | `active` | Split by registry/control/command responsibility; remaining route should stay thin. | Keep endpoint contracts stable and guard against orchestration creep. |

## Target Source Shape

Backend target:

```text
api/routes/
  agent_runs.py                  # thin route assembly or list/detail routes
  agent_runs_commands.py         # command + preflight endpoints
  agent_runs_registry.py         # registry, releases, audit, ownership endpoints
  agent_runs_control.py          # start/pause/cancel/step endpoints
application/services/agent_runtime/
  capabilities/
    executor.py                  # capability execution
    support.py                   # capability helper logic
    types.py                     # shared capability runtime types
  commands/
    service.py                   # command orchestration and receipts
    preflight.py                 # command preflight and command event receipts
    recovery.py                  # retry/recovery/compensating proposal construction
    decisions.py                 # approve/reject mutation and audit events
  registry/
    catalog.py                   # static specs, profiles, recovery templates
    contracts.py                 # registry serialization, fingerprinting, schema validation
  runtime/
    service.py                   # lock, policy, execution, status transitions
    audit.py                     # run/action event construction
  policy.py                      # policy and capability authorization
```

Frontend target:

```text
web/components/agent-runs/
  RunList.tsx
  RunDetail.tsx
  ActionDetailPanel.tsx
  RegistryPanel.tsx
  ReleaseDetailPanel.tsx
web/components/agent/
  CommandComposer.tsx
  RecoveryControls.tsx
  PreflightPanel.tsx
  CompensatingProposalControl.tsx
web/components/interventions/
  InterventionQueue.tsx
  InterventionRow.tsx
```

Docs target:

```text
docs/
  README.md                      # canonical doc index and statuses
  agentification-checkpoint.md    # active checkpoint only
  agent-first-modular-architecture-v1.md
  operator-experience.md          # current operator/user guide
  agentic-layer.md
  ui-control-plane-simplification-plan.md
  ui-style-direction.md
  chat-led-operator-console-spec.md
  history/
    agent-first-migration-slice-rfc.md
    user-guide-complete.md
    experiment-flow-detailed.md
```

## PR Sequence

### PR 1: Inventory And Safe Hygiene

- Add this plan and a docs index/status map.
- Point Makefile and docs to canonical script modules.
- Keep compatibility wrappers in place.
- Fix cleanup guardrails so `make bloat-check` ignores local virtualenvs and recognizes known current hotspots.
- Do not delete `domain/`.

### PR 2: Script Consolidation

- Remove root script wrappers after references use canonical modules.
- Update any CI templates or docs still using wrapper paths.
- Keep `make` targets as the stable operator interface.
- Add an executable guardrail that fails when root-level script modules reappear.

### PR 3: Docs Canonicalisation

- Move historical docs under `docs/history/` or mark them clearly as historical.
- Replace old human-led user guide links with control-plane/agent-first guidance.
- Keep README linked only to current or reference docs.

### PR 4: Frontend Control-Plane Modularisation

- Split `web/app/agent-runs/page.tsx` into run list, run detail, registry, release, and action panels.
- PR4 started this by extracting the registry/release/backfill surface into `web/components/agent-runs/RegistryPanel.tsx`.
- The follow-up Agent Runs modularisation extracted the artifact diff drawer into `web/components/agent-runs/ActionDiffDrawer.tsx`.
- The next Agent Runs slice extracted budget guardrails, counters, and the action table into `web/components/agent-runs/RunActionsPanel.tsx`.
- The final slice in this PR extracted registry-aware selected-action details into `web/components/agent-runs/SelectedActionDetailPanel.tsx`.
- The Operator Chat split extracted summary, quick prompts, transcript rendering, command/recovery controls, and navigation/focus controls into smaller components under `web/components/agent/`.
- The follow-up Operator Chat cleanup moved reusable chat labels, risk labels, recovery preferences, and command outcome formatting into `operatorChatLogic.ts`, removed unused duplicate prompt/type modules, and lowered the parent bloat cap.
- The Interventions cleanup moved queue item types, risk/priority classification, and queue rendering sections into `web/components/interventions/`, reducing the page to routing, loading, command handlers, and layout.
- Continue extracting deeper chat orchestration helpers only if the parent starts growing again.
- Keep behavior unchanged and rely on existing Vitest coverage.

### PR 5: Backend Agent Runtime Modularisation

- Split `api/routes/agent_runs.py` by responsibility.
- PR5 started this by extracting registry/release/ownership/backfill endpoints into `api/routes/agent_runs_registry.py`.
- The next PR5 slice extracted start/pause/cancel/step/tick control endpoints into `api/routes/agent_runs_control.py`.
- The command slice extracted preflight, operator command execution, recovery proposal, retry proposal, and action decision endpoints into `api/routes/agent_runs_commands.py`.
- The command service slice moved reusable command preflight helpers into `application/services/agent_runtime/commands/preflight.py` and recovery template, retry metadata, rollback, and compensating-action helpers into `application/services/agent_runtime/commands/recovery.py`.
- The route-thinning slice wired command routes to the command service for change-plan proposals, retry proposals, and action decisions, then lowered the route bloat cap to prevent regression.
- The recovery split moved recovery templates, rollback guidance, compensating actions, change-plan proposal creation, and retry proposal creation into `application/services/agent_runtime/commands/recovery.py`, with dedicated bloat caps for both command and recovery services.
- The decision split moved action approve/reject mutation and audit-event writing into `application/services/agent_runtime/commands/decisions.py`, leaving `commands/preflight.py` focused on preflight and command receipts.
- The run-creation split moved initial plan/action seeding into `application/services/agent_runtime/runs.py`, kept registry materialization in `api/utils/agent_registry_runtime.py` because it touches infrastructure, and left `api/routes/agent_runs.py` as request/principal handling plus read endpoints.
- The registry approval split moved receipt signing, receipt verification, and ownership preflight into `api/utils/agent_registry_approvals.py`, leaving `api/routes/agent_runs_registry.py` focused on registry endpoints.
- The capability support split moved shared variant selection, validation readiness, copy-revision lookup, and numeric helpers into `application/services/agent_runtime/capabilities/support.py`, with shared runtime types in `capabilities/types.py`.
- The registry catalog split moved static tool/capability specs, policy profiles, and recovery template definitions into `application/services/agent_runtime/registry/catalog.py`, leaving `registry/contracts.py` focused on contract serialization, fingerprinting, version context, and schema validation.
- The runtime audit split moved run/action event construction into `application/services/agent_runtime/runtime/audit.py`, leaving `runtime/service.py` focused on lock, policy, execution, and status transitions.
- The package reorganisation moved capability, command, registry, and runtime modules into subpackages while preserving package-level re-exports for existing imports.
- The command orchestration split moved command context loading, preflight response assembly, command receipt writing, recovery/retry mutation dispatch, decisions, and runtime command dispatch into `application/services/agent_runtime/commands/service.py`, leaving `api/routes/agent_runs_commands.py` as HTTP translation only.
- Continue extracting only if command-specific flows grow enough to need separate services.
- Keep endpoint contracts stable.

### PR 6: Guardrail Tightening

- Lower bloat thresholds after hotspots are split.
- Add a duplicate-script check once wrappers are removed.
- Add an architecture guardrail that keeps command routes behind `commands/service.py` instead of re-importing low-level command internals.
- Add doc status enforcement if docs continue growing.

## Verification Baseline

Run these for cleanup PRs:

```bash
make lint
make arch-check
make bloat-check
make script-entrypoint-check
venv/bin/python -m pytest tests/test_agent_runs_api.py tests/modules/test_agent_capability_registry.py tests/modules/test_agent_runtime_service.py
cd web && pnpm exec vitest run app/agent-runs/page.test.tsx components/agent/OperatorConsoleChat.test.tsx app/interventions/page.test.tsx
cd web && NEXT_PUBLIC_AUTH_MODE=mock NEXT_PUBLIC_ALLOW_MOCK_AUTH_IN_PRODUCTION=true pnpm run build
```
