# Codebase Cleanup And Modularisation Plan

Status: current
Last updated: 2026-05-04

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
| `docs/chat-led-operator-console-spec.md` | `current/reference` | Still relevant to control-plane UX. | Keep, trim only after UI settles. |
| `docs/user-guide-complete.md` | `historical-candidate` | Written for older human-led UX. | Mark historical or replace with control-plane user guide. |
| `docs/experiment-flow-detailed.md` | `historical-candidate` | Lab-era flow detail. | Move to historical after README no longer points to it as active. |
| `docs/app-workflows.md` | `reference/historical-candidate` | Contains useful workflow notes but overlaps newer checkpoint docs. | Split current API facts from history. |
| largest frontend pages | `active-hotspot` | `experiments`, `agent-runs`, `admin`, `validation` are expensive to load/change. | Modularise by surface after cleanup PRs. |
| `api/routes/agent_runs.py` | `active-hotspot` | Route file now owns too many registry/command/control concerns. | Split after frontend control-plane cleanup. |

## Target Source Shape

Backend target:

```text
api/routes/
  agent_runs.py                  # thin route assembly or list/detail routes
  agent_runs_commands.py         # command + preflight endpoints
  agent_runs_registry.py         # registry, releases, audit, ownership endpoints
  agent_runs_control.py          # start/pause/cancel/step endpoints
application/services/agent_runtime/
  command_service.py             # command orchestration and receipts
  recovery.py                    # retry/recovery/compensating proposal construction
  registry.py                    # registry contract, metadata, fingerprinting
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
  agentic-layer.md
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
- Continue extracting `OperatorConsoleChat` into command composer, recovery controls, and preflight panel.
- Keep behavior unchanged and rely on existing Vitest coverage.

### PR 5: Backend Agent Runtime Modularisation

- Split `api/routes/agent_runs.py` by responsibility.
- Move recovery and compensating action construction into an application service module.
- Keep endpoint contracts stable.

### PR 6: Guardrail Tightening

- Lower bloat thresholds after hotspots are split.
- Add a duplicate-script check once wrappers are removed.
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
